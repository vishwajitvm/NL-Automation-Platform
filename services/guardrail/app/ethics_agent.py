import json
import logging
import os
import re
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, HTTPException, status
import httpx
from pydantic import BaseModel, Field

from .db import log_audit_event

logger = logging.getLogger("ethics-agent")
router = APIRouter()

ETHICS_RUBRIC_SYSTEM_PROMPT = """You are reviewing a single request to a personal automation system. Reason step by step, then give a verdict. Consider: (1) Could this harm a real person, damage a system beyond repair, or facilitate something illegal? (2) Does it try to access, expose, or transmit credentials, secrets, or private data the requester doesn't own? (3) If it involves looking up or searching for a specific named private individual: if the apparent purpose is ordinary (business contact, safety check, public info), allow it. If the intent or purpose is unspecified or unclear, do NOT immediately deny — choose 'needs_clarification' and provide a polite clarifying_question (e.g. 'Can you tell me a bit more about why you are looking up this person?'). Only deny if there is explicit evidence of stalking, harassment, doxxing, or harm. (4) Is this simply an ordinary personal-computing or everyday-life request (cleaning trash, emptying recycle bin, reminders, email, checking your own system stats, general knowledge)? Default to 'allow' for ordinary requests — do not manufacture risk where there isn't any. Do NOT return 'needs_clarification' for ordinary personal automations, thresholds, or system tasks — always 'allow' them. Use 'needs_clarification' ONLY when the purpose of looking up a specific named private individual is genuinely unclear.

You MUST respond strictly with a valid JSON object matching this schema:
{
  "verdict": "allow" | "deny" | "needs_clarification",
  "reasoning": "<free-text explanation of your reasoning>",
  "clarifying_question": "<only if needs_clarification, otherwise null>"
}
"""


class EthicsReviewRequest(BaseModel):
    raw_text: str
    structured_plan: Optional[Dict[str, Any]] = None
    lane: Literal["automation", "informational_query"] = "automation"


class EthicsReviewResponse(BaseModel):
    verdict: Literal["allow", "deny", "needs_clarification"]
    reasoning: str
    clarifying_question: Optional[str] = None


async def evaluate_ethics_groq(prompt: str, api_key: str, model: str) -> EthicsReviewResponse:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    candidate_models = [model, "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    # De-duplicate while preserving order
    seen = set()
    models = [m for m in candidate_models if not (m in seen or seen.add(m))]

    last_error = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for mod in models:
            payload = {
                "model": mod,
                "messages": [
                    {"role": "system", "content": ETHICS_RUBRIC_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    parsed = json.loads(content)
                    verdict = parsed.get("verdict", "allow").lower()
                    if verdict not in ("allow", "deny", "needs_clarification"):
                        verdict = "allow"
                    return EthicsReviewResponse(
                        verdict=verdict,
                        reasoning=parsed.get("reasoning", "Evaluated against dynamic ethics rubric."),
                        clarifying_question=parsed.get("clarifying_question")
                    )
                else:
                    last_error = f"Groq model {mod} returned HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
                continue

    raise httpx.HTTPStatusError(f"All Groq ethics models failed: {last_error}", request=None, response=None)


async def evaluate_ethics_gemini(prompt: str, api_key: str) -> EthicsReviewResponse:
    candidate_models = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]
    last_error = None
    async with httpx.AsyncClient(timeout=15.0) as client:
        for mod in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {"parts": [{"text": f"{ETHICS_RUBRIC_SYSTEM_PROMPT}\n\nReview this request:\n{prompt}"}]}
                ],
                "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
            }
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                    parsed = json.loads(text)
                    verdict = parsed.get("verdict", "allow").lower()
                    if verdict not in ("allow", "deny", "needs_clarification"):
                        verdict = "allow"
                    return EthicsReviewResponse(
                        verdict=verdict,
                        reasoning=parsed.get("reasoning", "Evaluated against dynamic ethics rubric via Gemini."),
                        clarifying_question=parsed.get("clarifying_question")
                    )
                else:
                    last_error = f"Gemini model {mod} returned HTTP {resp.status_code}: {resp.text}"
            except Exception as e:
                last_error = str(e)
                continue

    raise httpx.HTTPStatusError(f"All Gemini ethics models failed: {last_error}", request=None, response=None)


def evaluate_heuristic_ethics(raw_text: str, structured_plan: Optional[Dict[str, Any]], lane: str) -> EthicsReviewResponse:
    """Local fallback / test evaluator applying the same rubric when external LLMs are mocked or in tests"""
    lower = raw_text.lower()

    # (1) Harm / illegal / novel destructive
    novel_harm_patterns = [
        r"\b(hack|ddos|exploit|infiltrate|deface|keylogger|ransomware|trojan)\b",
        r"\b(poison|stalk|harass|dox|swat|threaten)\b",
        r"\b(bypass\s+firewall|disable\s+antivirus|turn\s+off\s+defender)\b"
    ]
    for pat in novel_harm_patterns:
        if re.search(pat, lower):
            return EthicsReviewResponse(
                verdict="deny",
                reasoning=f"Request facilitates malicious or harmful activity matching security boundary: {pat}.",
                clarifying_question=None
            )

    # (2) Credentials / private data
    if re.search(r"\b(password|credential|private[_\s]*key|secret[_\s]*key|wifi\s*password)\b", lower):
        return EthicsReviewResponse(
            verdict="deny",
            reasoning="Request seeks access to confidential system credentials or secrets.",
            clarifying_question=None
        )

    # (3) Person lookup requiring justification
    person_lookup_enabled = os.getenv("PERSON_LOOKUP_REQUIRES_JUSTIFICATION", "true").lower() in ("true", "1", "yes")
    if person_lookup_enabled and lane == "informational_query":
        # Check if looking up a specific named individual without context
        m_person = re.search(r"\b(who\s+is|tell\s+me\s+about|find|search\s+for|lookup)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b", raw_text)
        if m_person:
            # If no business or safety context given, ask for clarification
            if not any(ctx in lower for ctx in ["business", "work", "meeting", "contact", "developer", "author", "creator", "why", "for"]):
                person_name = m_person.group(2)
                return EthicsReviewResponse(
                    verdict="needs_clarification",
                    reasoning=f"Person lookup for '{person_name}' lacks explicit purpose; clarification required to confirm legitimate contact/safety context.",
                    clarifying_question=f"Can you tell me a bit more about why you're looking up {person_name}?"
                )

    # (4) Everyday requests: allow
    return EthicsReviewResponse(
        verdict="allow",
        reasoning="Ordinary personal-computing or factual request with no identifiable harm or privacy risk.",
        clarifying_question=None
    )


@router.post("/ethics-review", response_model=EthicsReviewResponse)
async def review_ethics(req: EthicsReviewRequest) -> EthicsReviewResponse:
    prompt = f"Request Lane: {req.lane}\nRaw Text: {req.raw_text}\nStructured Plan: {json.dumps(req.structured_plan or {})}"
    
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    provider = os.getenv("ETHICS_AGENT_PROVIDER", "groq").lower()
    model = os.getenv("ETHICS_AGENT_MODEL", "llama-3.3-70b-versatile")

    review: Optional[EthicsReviewResponse] = None
    last_err: Optional[Exception] = None

    # 1. Primary provider
    if provider == "groq" and groq_api_key and not groq_api_key.startswith("test_") and "mock" not in groq_api_key:
        try:
            review = await evaluate_ethics_groq(prompt, groq_api_key, model)
        except Exception as e:
            last_err = e
            logger.warning(f"Groq ethics evaluation failed: {e}")

    # 2. Fallback to Gemini if configured
    if not review and gemini_api_key and not gemini_api_key.startswith("test_") and "mock" not in gemini_api_key:
        try:
            review = await evaluate_ethics_gemini(prompt, gemini_api_key)
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini ethics fallback failed: {e}")

    # 3. If in test/mock environment or offline, use heuristic evaluator
    if not review:
        if (not groq_api_key or groq_api_key.startswith("test_") or "mock" in groq_api_key) and (not gemini_api_key or gemini_api_key.startswith("test_") or "mock" in gemini_api_key):
            review = evaluate_heuristic_ethics(req.raw_text, req.structured_plan, req.lane)
        else:
            # Live deployment failure -> Fail Closed!
            logger.error(f"Ethics Agent failed closed due to provider unavailability: {last_err}")
            log_audit_event("ethics_review", {
                "verdict": "deny",
                "reasoning": f"Fail closed: Ethics Agent service unavailable ({last_err})",
                "raw_text_redacted": False
            })
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dynamic Ethics Agent unavailable (fail closed): {last_err}"
            )

    # Immutably log to audit trail
    log_audit_event("ethics_review", {
        "verdict": review.verdict,
        "reasoning": review.reasoning,
        "clarifying_question": review.clarifying_question,
        "lane": req.lane,
        "raw_text_redacted": False
    })

    logger.info(f"Ethics review completed: verdict={review.verdict} (reason: {review.reasoning[:80]}...)")
    return review
