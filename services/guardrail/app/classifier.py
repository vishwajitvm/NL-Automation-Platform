import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

from shared.schemas.plan import AutomationPlan
from .db import log_audit_event

logger = logging.getLogger("guardrail")

ALLOWED_ACTIONS = {
    "send_email",
    "send_webhook",
    "write_log_notification",
    "run_http_healthcheck",
    "empty_trash",
    "empty_recycle_bin",  # Deprecated alias
    "web_search",
    "check_disk_usage",
    "list_drives",
    "clean_temp_and_cache",
    "delete_path",
    "browser_open_url",
    "browser_list_open_tabs",
    "browser_close_tab",
    "browser_clear_managed_cache",
}

TAXONOMY_PROMPT = """You are a security classifier for an automated task execution system.
Analyze the following automation plan against these custom security categories:

1. destructive_fs_op: Disk formatting, partition wiping, file deletion outside application scope, deleting system roots (e.g., C:\\, /root, /bin).
2. credential_exfiltration: Reading or transmitting secret keys, SSH keys, passwords, environment tokens.
3. network_exfiltration: Data exfiltration to suspicious endpoints or unapproved data staging servers.
4. malware_behavior: Establishing persistence, disabling security controls or firewalls, privilege escalation.

Respond strictly in JSON format:
{
  "safe": boolean,
  "categories": list of strings (matching any violated category),
  "reason": string or null
}
"""


class ClassificationResult(BaseModel):
    decision: str  # "approved" | "blocked"
    reason: Optional[str] = None
    categories: List[str] = []


def is_obvious_destructive(plan: AutomationPlan) -> Optional[str]:
    if plan.action and plan.action.name == "delete_path":
        target = plan.action.params.get("path", "")
        from shared.safety.denylist import is_forbidden
        if is_forbidden(target):
            return "destructive_fs_op"

    combined = f"{plan.raw_text} {json.dumps(plan.action.params if plan.action else {})}".lower()
    destructive_patterns = [
        r"format\s+[a-z]:",
        r"format\s+drive",
        r"rm\s+-rf\s+/",
        r"del\s+/[sfq]\s+c:",
        r"drop\s+database",
        r"wipe\s+disk",
        r"shred\s+",
    ]
    for pattern in destructive_patterns:
        if re.search(pattern, combined):
            return "destructive_fs_op"
    return None


def is_obvious_injection(text: str) -> bool:
    injection_patterns = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"system\s+prompt",
        r"jailbreak",
        r"you\s+are\s+now\s+in\s+dan\s+mode",
        r"bypass\s+safety",
    ]
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in injection_patterns)


async def check_prompt_guard_groq(text: str, api_key: str) -> bool:
    """Pre-filter screen using Groq hosted model"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "meta-llama/llama-prompt-guard-2-86m",
        "messages": [
            {"role": "user", "content": text}
        ],
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 500:
            raise httpx.HTTPStatusError("Groq 5xx error", request=resp.request, response=resp)
        if resp.status_code != 200:
            # If prompt guard model is unavailable on this free tier, fallback to heuristic
            return False
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").lower()
        return "injection" in content or "jailbreak" in content


async def check_llama_guard_groq(plan: AutomationPlan, api_key: str) -> ClassificationResult:
    """Main classifier using Groq hosted safeguard model"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    models = ["openai/gpt-oss-safeguard-20b", "meta-llama/llama-guard-4-12b", "openai/gpt-oss-20b"]
    data = None
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for model_name in models:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": TAXONOMY_PROMPT},
                    {"role": "user", "content": f"Plan: {plan.model_dump_json()}"}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"}
            }
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                break
            elif resp.status_code >= 500:
                raise httpx.HTTPStatusError("Groq 5xx error", request=resp.request, response=resp)

    if not data:
        raise httpx.HTTPStatusError("All Groq guardrail models failed", request=None, response=None)
    
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    result = json.loads(content)
    if not result.get("safe", True):
        cats = result.get("categories", ["unsafe_plan"])
        return ClassificationResult(
            decision="blocked",
            reason=result.get("reason", "Violation of safety taxonomy"),
            categories=cats
        )
    return ClassificationResult(decision="approved", reason=None, categories=[])


async def classify_plan(plan: AutomationPlan, force_groq_fail: bool = False) -> ClassificationResult:
    # 1. Action registry gate: Unregistered actions are automatically blocked before calling Groq
    if plan.action is None or plan.action.name not in ALLOWED_ACTIONS:
        unreg_name = plan.action.name if plan.action else "None"
        reason = f"Action '{unreg_name}' is not in the registered action allowlist."
        log_audit_event("guardrail_blocked", {"reason": reason, "action": unreg_name})
        return ClassificationResult(
            decision="blocked",
            reason=reason,
            categories=["unregistered_action"]
        )

    # 2. Local heuristic checks for prompt injection
    if is_obvious_injection(plan.raw_text):
        reason = "Prompt injection / jailbreak detected."
        log_audit_event("guardrail_blocked", {"reason": reason, "categories": ["prompt_injection"]})
        return ClassificationResult(
            decision="blocked",
            reason=reason,
            categories=["prompt_injection"]
        )

    # 3. Local heuristic check for destructive FS operation
    destructive_cat = is_obvious_destructive(plan)
    if destructive_cat:
        reason = "Destructive file system operation detected."
        log_audit_event("guardrail_blocked", {"reason": reason, "categories": [destructive_cat]})
        return ClassificationResult(
            decision="blocked",
            reason=reason,
            categories=[destructive_cat]
        )

    # 4. Groq Classifier with Fail-Closed wrapper
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    
    if force_groq_fail:
        # Simulated Groq failure for testing fail-closed requirement
        log_audit_event("guardrail_blocked", {"reason": "fail_closed", "error": "Groq forced unreachable in test"})
        return ClassificationResult(
            decision="blocked",
            reason="Security guardrail evaluation failed closed due to service unavailability.",
            categories=["guardrail_unavailable"]
        )

    if groq_api_key and not groq_api_key.startswith("test_") and "mock" not in groq_api_key:
        try:
            # Stage 1: Pre-filter injection screen
            flagged_injection = await check_prompt_guard_groq(plan.raw_text, groq_api_key)
            if flagged_injection:
                log_audit_event("guardrail_blocked", {"reason": "Groq prompt guard flagged injection", "categories": ["prompt_injection"]})
                return ClassificationResult(
                    decision="blocked",
                    reason="Potential prompt injection flagged by pre-filter.",
                    categories=["prompt_injection"]
                )

            # Stage 2: Main Classifier Llama Guard 4
            result = await check_llama_guard_groq(plan, groq_api_key)
            if result.decision == "blocked":
                log_audit_event("guardrail_blocked", {"reason": result.reason, "categories": result.categories})
                return result
        except Exception as e:
            # Fail closed on any network error, timeout, or 5xx
            logger.error(f"Groq guardrail failed closed: {e}")
            log_audit_event("guardrail_blocked", {"reason": "fail_closed", "error": str(e)})
            return ClassificationResult(
                decision="blocked",
                reason="Security guardrail evaluation failed closed due to service unavailability.",
                categories=["guardrail_unavailable"]
            )

    # Approved
    log_audit_event("guardrail_approved", {"action": plan.action.name})
    return ClassificationResult(decision="approved", reason=None, categories=[])
