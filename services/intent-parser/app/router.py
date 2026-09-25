import json
import logging
import os
import re
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel

from .db import log_audit_event

logger = logging.getLogger("request-router")
router = APIRouter()

STANDARD_REFUSAL_GENERAL = "I cannot assist with requests involving the purchase, procurement, or manufacture of illegal substances or weapons."
STANDARD_REFUSAL_SUBSTANCE = "I cannot help with obtaining controlled substances. If you or someone you know is seeking confidential support for substance use, you can contact SAMHSA's National Helpline at 1-800-662-4357."
STANDARD_REFUSAL_CRISIS = "I cannot fulfill this request. If you are experiencing thoughts of self-harm or need immediate support, please call or text 988 to reach the Suicide & Crisis Lifeline."


class RouteRequest(BaseModel):
    raw_text: str


class RouteResponse(BaseModel):
    lane: Literal["automation", "informational_query", "disallowed_content"]
    reason: str
    refusal: Optional[str] = None


# Heuristic patterns for default MLCommons hazard taxonomy
DISALLOWED_PATTERNS = [
    (r"\b(buy|purchase|obtain|get|sell)\s+(drugs|cocaine|heroin|meth|fentanyl|weed|narcotics|weed|lsd)\b", "illicit_goods_procurement", STANDARD_REFUSAL_SUBSTANCE),
    (r"\bwhere\s+can\s+i\s+(buy|get|find)\s+drugs\b", "illicit_goods_procurement", STANDARD_REFUSAL_SUBSTANCE),
    (r"\b(buy|make|build|assemble)\s+(a\s+)?(bomb|explosive|ghost gun|weapon)\b", "weapons_and_explosives", STANDARD_REFUSAL_GENERAL),
    (r"\b(how\s+to\s+)?(commit\s+suicide|kill\s+myself|self\s*harm)\b", "suicide_and_self_harm", STANDARD_REFUSAL_CRISIS),
    (r"\b(child\s+porn|csam)\b", "child_sexual_exploitation", STANDARD_REFUSAL_GENERAL),
]

INFORMATIONAL_PATTERNS = [
    r"^(what|who|where|how much|how many|is there|show me|check|list)\b",
    r"\b(temperature|weather|free space|disk usage|drives)\b",
    r"^search\s+(for\s+)?",
]

AUTOMATION_TRIGGERS = [
    r"\bevery\s+(minute|hour|day|week|month|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b",
    r"\bwhen\s+(it|the|disk|trash|usage|metric|system)\b",
    r"\bwhenever\b",
    r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b",
    r"\bcron\b",
    r"\bschedule\b",
    r"\bautomatically\b",
]


async def check_default_llama_guard(text: str, api_key: str) -> Optional[Dict[str, str]]:
    """Evaluates raw_text against default Groq Llama Guard 4 hazard taxonomy."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "meta-llama/llama-guard-4-12b",
        "messages": [
            {"role": "user", "content": text}
        ],
        "temperature": 0.0
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if content.lower().startswith("unsafe"):
                    # content often has 'unsafe\nS1' or similar
                    lines = content.splitlines()
                    category = lines[1] if len(lines) > 1 else "content_hazard"
                    return {"category": category, "reason": "Violated Llama Guard hazard taxonomy"}
            elif resp.status_code >= 500:
                logger.warning(f"Groq returned 5xx for Llama Guard check: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Error querying Groq Llama Guard: {e}")
    return None


@router.post("/route", response_model=RouteResponse)
async def route_request(body: RouteRequest) -> RouteResponse:
    text = body.raw_text.strip()
    if not text:
        return RouteResponse(lane="automation", reason="Empty text routed to parser fallback")

    text_lower = text.lower()

    # 1. Deterministic heuristic check for content policy
    for pattern, category, refusal in DISALLOWED_PATTERNS:
        if re.search(pattern, text_lower):
            log_audit_event(
                event_type="content_policy_blocked",
                payload={"category": category, "reason": "Keyword heuristic match against hazard taxonomy", "raw_text_redacted": True}
            )
            return RouteResponse(
                lane="disallowed_content",
                reason=f"Violated content policy hazard taxonomy: {category}",
                refusal=refusal
            )

    # 2. Check Groq Llama Guard default hazard taxonomy if API key is configured
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and not groq_key.startswith("mock_"):
        guard_result = await check_default_llama_guard(text, groq_key)
        if guard_result:
            cat = guard_result.get("category", "content_hazard")
            log_audit_event(
                event_type="content_policy_blocked",
                payload={"category": cat, "reason": guard_result.get("reason", "Llama Guard default hazard violation"), "raw_text_redacted": True}
            )
            refusal_text = STANDARD_REFUSAL_SUBSTANCE if "drug" in text_lower else STANDARD_REFUSAL_GENERAL
            return RouteResponse(
                lane="disallowed_content",
                reason=f"Violated content policy hazard taxonomy: {cat}",
                refusal=refusal_text
            )

    # 3. Check if automation trigger is present
    has_trigger = any(re.search(pat, text_lower) for pat in AUTOMATION_TRIGGERS)
    if has_trigger:
        return RouteResponse(lane="automation", reason="Input contains scheduling or threshold automation trigger")

    # 4. Check if informational query
    is_info = any(re.search(pat, text_lower) for pat in INFORMATIONAL_PATTERNS)
    if is_info:
        return RouteResponse(lane="informational_query", reason="One-off factual or system inquiry without automation schedule")

    # Default: route to automation pipeline
    return RouteResponse(lane="automation", reason="Default action/automation candidate")
