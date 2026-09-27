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
CREDENTIAL_REFUSAL_FIXED = "I'm sorry, but this information is not allowed to be shared — we cannot share system credentials with anyone."


class RouteRequest(BaseModel):
    raw_text: str


class RouteResponse(BaseModel):
    lane: Literal["automation", "informational_query", "disallowed_content"]
    reason: str
    refusal: Optional[str] = None
    target_action: Optional[str] = None
    target_params: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None


# Priority 0: Credential Exfiltration Patterns (§10.6 fixed refusal)
CREDENTIAL_PATTERNS = [
    r"\b(wifi|wi-fi|admin|administrator|root|system|account|user|computer|database|db|windows|linux|ssh)\s*(password|passwords|credential|credentials|secret|secrets)\b",
    r"\b(password|passwords|credential|credentials)\s*(of|for)\b",
    r"\b(what('?s| is)|show|give|tell|find|get)\s+.*(password|passwords|credential|credentials)\b",
    r"\b(api[_\s-]*key|access[_\s-]*token|private[_\s-]*key|secret[_\s-]*key)\b",
]

# Heuristic patterns for default MLCommons hazard taxonomy
DISALLOWED_PATTERNS = [
    (r"\b(buy|purchase|obtain|get|sell)\s+(drugs|cocaine|heroin|meth|fentanyl|weed|narcotics|weed|lsd)\b", "illicit_goods_procurement", STANDARD_REFUSAL_SUBSTANCE),
    (r"\bwhere\s+can\s+i\s+(buy|get|find)\s+drugs\b", "illicit_goods_procurement", STANDARD_REFUSAL_SUBSTANCE),
    (r"\b(buy|make|build|assemble)\s+(a\s+)?(bomb|explosive|ghost gun|weapon)\b", "weapons_and_explosives", STANDARD_REFUSAL_GENERAL),
    (r"\b(how\s+to\s+)?(commit\s+suicide|kill\s+myself|self\s*harm)\b", "suicide_and_self_harm", STANDARD_REFUSAL_CRISIS),
    (r"\b(child\s+porn|csam)\b", "child_sexual_exploitation", STANDARD_REFUSAL_GENERAL),
]

INFORMATIONAL_PATTERNS = [
    r"^(what|who|where|how much|how many|is there|show me|check|list|tell me about)\b",
    r"\b(temperature|weather|free space|disk usage|drives|ram|memory|devices|processes)\b",
    r"^search\s+(for\s+)?",
]

AUTOMATION_TRIGGERS = [
    r"\bevery\s+(minute|hour|day|week|month|friday|monday|tuesday|wednesday|thursday|saturday|sunday)\b",
    r"\bwhen\s+(it|the|disk|trash|usage|metric|system)\b",
    r"\bwhenever\b",
    r"\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b",
    r"\b(?:after|in)\s+\d+\s*(minute|minutes|min|mins|hour|hours|second|seconds|sec|secs)\b",
    r"\bremind\s+me\b",
    r"\bemail\s+me\b",
    r"\b(clean|empty)\s+(my\s+)?(recycle\s+bin|trash)\b",
    r"\bcron\b",
    r"\bschedule\b",
    r"\bautomatically\b",
]


async def check_default_llama_guard(text: str, api_key: str) -> Optional[Dict[str, str]]:
    """Evaluates raw_text against default Groq safeguard hazard taxonomy."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    models = ["openai/gpt-oss-safeguard-20b", "meta-llama/llama-guard-4-12b", "openai/gpt-oss-20b"]

    for model_name in models:
        payload = {
            "model": model_name,
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
                        lines = content.splitlines()
                        category = lines[1] if len(lines) > 1 else "content_hazard"
                        return {"category": category, "reason": "Violated safeguard hazard taxonomy"}
                    return None
                elif resp.status_code >= 500:
                    logger.warning(f"Groq returned 5xx for safeguard check: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error querying Groq safeguard: {e}")
    return None


@router.post("/route", response_model=RouteResponse)
async def route_request(body: RouteRequest) -> RouteResponse:
    text = body.raw_text.strip()
    if not text:
        return RouteResponse(lane="automation", reason="Empty text routed to parser fallback")

    text_lower = text.lower()

    # Phase 12 disambiguation
    if re.search(r"how many.*tasks.*running|what.*tasks.*running", text_lower):
        return RouteResponse(
            lane="informational_query",
            reason="Ambiguous 'tasks' query",
            needs_clarification=True,
            clarifying_question="Do you mean apps running on your computer, tabs open in your browser, or your own active automations?"
        )


    # 0. Deterministic credential check (§10.6 fixed refusal)
    for pat in CREDENTIAL_PATTERNS:
        if re.search(pat, text_lower):
            log_audit_event(
                event_type="content_policy_blocked",
                payload={"category": "credential_exfiltration", "reason": "Credential exfiltration pattern match", "raw_text_redacted": True}
            )
            return RouteResponse(
                lane="disallowed_content",
                reason="credential_exfiltration",
                refusal=CREDENTIAL_REFUSAL_FIXED
            )

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

    # 4. Check if informational query or system diagnostics
    is_info = any(re.search(pat, text_lower) for pat in INFORMATIONAL_PATTERNS)
    if is_info:
        # Determine specific read-only target action
        if "device" in text_lower or "connected" in text_lower or "plugged" in text_lower:
            return RouteResponse(
                lane="informational_query",
                reason="System diagnostic query: connected devices",
                target_action="list_connected_devices",
                target_params={}
            )
        elif "process" in text_lower or "taskmanager" in text_lower or "task manager" in text_lower or "consuming" in text_lower or "chrome" in text_lower:
            return RouteResponse(
                lane="informational_query",
                reason="System diagnostic query: top processes",
                target_action="list_top_processes",
                target_params={"sort_by": "memory", "limit": 10}
            )
        elif "ram" in text_lower or "memory" in text_lower:
            return RouteResponse(
                lane="informational_query",
                reason="System diagnostic query: memory usage",
                target_action="get_memory_usage",
                target_params={}
            )
        elif "drive" in text_lower and ("list" in text_lower or "how many" in text_lower or "show" in text_lower):
            return RouteResponse(
                lane="informational_query",
                reason="System diagnostic query: list drives",
                target_action="list_drives",
                target_params={}
            )
        elif "disk" in text_lower or "volume" in text_lower or "space" in text_lower:
            # Check drive letter
            m_drive = re.search(r"([A-Za-z]):", text)
            drive_path = f"{m_drive.group(1).upper()}:\\" if m_drive else ("C:\\" if os.name == "nt" else "/")
            return RouteResponse(
                lane="informational_query",
                reason="System diagnostic query: disk usage",
                target_action="check_disk_usage",
                target_params={"path": drive_path}
            )
        else:
            return RouteResponse(
                lane="informational_query",
                reason="Informational factual query",
                target_action="web_search",
                target_params={"query": text}
            )

    # Default: route to automation pipeline
    return RouteResponse(lane="automation", reason="Default action/automation candidate")
