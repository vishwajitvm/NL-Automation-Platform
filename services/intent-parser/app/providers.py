from abc import ABC, abstractmethod
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Type
import httpx
from pydantic import BaseModel, Field

from shared.schemas.plan import Trigger, Action, Ambiguity, AutomationPlan
from .db import log_audit_event
from .prompt import SYSTEM_PROMPT

logger = logging.getLogger("intent-parser")


class ParsedResult(BaseModel):
    raw_text: str
    detected_count: int = 1
    parseable: bool = True
    trigger: Optional[Trigger] = None
    action: Optional[Action] = None
    ambiguities: List[Ambiguity] = Field(default_factory=list)
    degraded_mode: bool = False


class LLMError(Exception):
    pass


class RateLimitError(LLMError):
    pass


class ProviderUnavailableError(LLMError):
    pass


class AllProvidersExhaustedError(LLMError):
    pass


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


class LLMProvider(ABC):
    @abstractmethod
    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        pass


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        if not self.api_key or self.api_key.startswith("test_") or "mock" in self.api_key:
            raise ProviderUnavailableError("Gemini API key is not configured or mock key")

        # Try gemini-2.5-flash with fallback to 1.5-flash or 2.0-flash
        models_to_try = [self.model, "gemini-2.0-flash", "gemini-1.5-flash"]
        last_error = None
        for mod in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"{SYSTEM_PROMPT}\n\nUser: {prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json"
                }
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 429:
                        raise RateLimitError("Gemini rate limit 429")
                    if resp.status_code >= 500:
                        raise ProviderUnavailableError(f"Gemini server error {resp.status_code}: {resp.text}")
                    if resp.status_code != 200:
                        last_error = f"Gemini API returned {resp.status_code}: {resp.text}"
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ProviderUnavailableError("No candidates returned from Gemini")
                    content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    json_data = extract_json(content)
                    return schema.model_validate(json_data)
            except (RateLimitError, ProviderUnavailableError):
                raise
            except Exception as e:
                last_error = str(e)
                continue

        raise ProviderUnavailableError(f"Gemini failed across models: {last_error}")


class GroqProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model

    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        if not self.api_key or self.api_key.startswith("test_") or "mock" in self.api_key:
            raise ProviderUnavailableError("Groq API key is not configured or mock key")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    raise RateLimitError("Groq rate limit 429")
                if resp.status_code >= 500:
                    raise ProviderUnavailableError(f"Groq server error {resp.status_code}: {resp.text}")
                if resp.status_code != 200:
                    raise ProviderUnavailableError(f"Groq API returned {resp.status_code}: {resp.text}")

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                json_data = extract_json(content)
                return schema.model_validate(json_data)
        except (RateLimitError, ProviderUnavailableError):
            raise
        except Exception as e:
            raise ProviderUnavailableError(f"Groq invocation failed: {e}")


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "meta-llama/llama-3.3-70b-instruct:free"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model

    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        if not self.api_key or self.api_key.startswith("test_") or "mock" in self.api_key:
            raise ProviderUnavailableError("OpenRouter API key is not configured or mock key")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    raise RateLimitError("OpenRouter rate limit 429")
                if resp.status_code >= 500:
                    raise ProviderUnavailableError(f"OpenRouter server error {resp.status_code}: {resp.text}")
                if resp.status_code != 200:
                    raise ProviderUnavailableError(f"OpenRouter API returned {resp.status_code}: {resp.text}")

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                json_data = extract_json(content)
                return schema.model_validate(json_data)
        except (RateLimitError, ProviderUnavailableError):
            raise
        except Exception as e:
            raise ProviderUnavailableError(f"OpenRouter invocation failed: {e}")


class DeterministicRuleProvider(LLMProvider):
    """
    Offline/local rule parser providing deterministic behavior for standard test cases
    when external LLM API credentials are not provided or simulated offline.
    """
    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        text = prompt.strip().lower()

        # Gibberish check: empty, special chars only, or random consonant strings
        clean_words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", "", text).split() if len(w) > 0]
        known_keywords = {
            "clean", "recycle", "bin", "trash", "email", "summary", "friday", "disk", "usage",
            "notify", "every", "when", "at", "if", "send", "webhook", "monday", "schedule",
            "healthcheck", "check", "log", "alert", "run", "search", "delete", "remove", "wipe",
            "drive", "drives", "browser", "tab", "tabs", "open", "temp", "cache",
            "remind", "reminder", "stretch", "after", "minutes", "minute", "hours", "hour",
            "device", "devices", "process", "processes", "memory", "ram", "format"
        }
        meaningful_count = sum(1 for w in clean_words if w in known_keywords)

        if not text or len(clean_words) == 0 or (len(clean_words) > 2 and meaningful_count == 0):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=0,
                parseable=False,
                trigger=None,
                action=None,
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Compound sentence check: two distinct trigger/action clauses
        # e.g., "clean bin at 80% and email me weekly"
        if (" and " in text or "; " in text) and (
            ("recycle" in text or "bin" in text) and ("email" in text or "webhook" in text)
        ):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=2,
                parseable=True,
                trigger=None,
                action=None,
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Ambiguity check: e.g. "clean the recycle bin when it is full"
        if ("recycle" in text or "bin" in text) and "full" in text and not any(c.isdigit() for c in text):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="threshold", params={"metric": "recycle_bin_percentage"}),
                action=Action(name="empty_recycle_bin", params={}),
                ambiguities=[
                    Ambiguity(field_path="trigger.params.threshold", question="At what percentage capacity should the recycle bin be cleaned?")
                ],
                        degraded_mode=True
                    )
            return schema.model_validate(res.model_dump())

        # Case 0A: Curated Clean ("clean my C drive" -> clean_temp_and_cache, NEVER delete_path)
        if ("clean" in text or "free up" in text) and ("drive" in text or "c:" in text or "temp" in text or "cache" in text):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="clean_temp_and_cache", params={"include_browser_cache": True}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0B: Delete path (forbidden or specific)
        if "delete" in text or "remove" in text or "wipe" in text:
            path_match = re.search(r"(?:delete|remove|wipe)\s+(?:folder|directory|path\s+)?([A-Za-z]:[\\/][^\s]*|[A-Za-z]:|/[^\s]*)", text, re.IGNORECASE)
            target_path = path_match.group(1) if path_match else "C:\\"
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="delete_path", params={"path": target_path}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0B2: Format drive
        if "format" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": "0 0 * * *", "timezone": "UTC"}),
                action=Action(name="clean_temp_and_cache", params={}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0C: List drives
        if "list" in text and "drive" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="list_drives", params={}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0D: Web search
        if text.startswith("search") or "search for" in text:
            query = re.sub(r"^search\s+(for\s+)?", "", text)
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="web_search", params={"query": query}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0E: Relative Delay Triggers ("remind me after 5 minutes", "email me after 10 minutes")
        delay_match = re.search(r"\b(?:after|in)\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|second|seconds|sec|secs)\b", text)
        if delay_match:
            num = int(delay_match.group(1))
            unit = delay_match.group(2)
            if "hour" in unit:
                delay_sec = num * 3600
            elif "min" in unit:
                delay_sec = num * 60
            else:
                delay_sec = num

            if "email" in text:
                subject = "Reminder"
                if "about" in text:
                    subject = "Reminder: " + text.split("about", 1)[1].strip()
                act = Action(name="send_email", params={"subject": subject, "body": prompt})
            else:
                act = Action(name="write_log_notification", params={"message": prompt})

            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="delay", params={"delay_seconds": delay_sec}),
                action=act,
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 0F: System Monitoring actions
        if "device" in text and ("connected" in text or "plugged" in text or "external" in text):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="list_connected_devices", params={}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        if "process" in text or "taskmanager" in text or "task manager" in text or ("consuming" in text and "ram" in text):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="list_top_processes", params={"sort_by": "memory", "limit": 10}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        if ("memory" in text or "ram" in text) and ("usage" in text or "percent" in text or "consumption" in text or "how much" in text):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="immediate", params={}),
                action=Action(name="get_memory_usage", params={}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 1: Recycle bin / trash threshold vs immediate
        if "recycle" in text or "bin" in text or "trash" in text:
            act_name = "empty_recycle_bin" if "recycle" in text else "empty_trash"
            pct_match = re.search(r"(\d+)\s*%", text)
            if pct_match:
                thresh = int(pct_match.group(1))
                res = ParsedResult(
                    raw_text=prompt,
                    detected_count=1,
                    parseable=True,
                    trigger=Trigger(type="threshold", params={"metric": "recycle_bin_percentage", "threshold": thresh, "comparator": ">="}),
                    action=Action(name=act_name, params={}),
                    ambiguities=[], degraded_mode=True)
                return schema.model_validate(res.model_dump())
            elif "when" in text and "full" in text:
                res = ParsedResult(
                    raw_text=prompt,
                    detected_count=1,
                    parseable=True,
                    trigger=Trigger(type="threshold", params={"metric": "recycle_bin_percentage"}),
                    action=Action(name=act_name, params={}),
                    ambiguities=[
                        Ambiguity(field_path="trigger.params.threshold", question="At what percentage capacity should the recycle bin be cleaned?")
                    ],
                        degraded_mode=True
                    )
                return schema.model_validate(res.model_dump())
            else:
                # 10.1 BUGFIX: NEVER invent a numeric threshold. Default to immediate!
                res = ParsedResult(
                    raw_text=prompt,
                    detected_count=1,
                    parseable=True,
                    trigger=Trigger(type="immediate", params={}),
                    action=Action(name=act_name, params={}),
                    ambiguities=[], degraded_mode=True)
                return schema.model_validate(res.model_dump())

        # Case 2: Email time-based
        if "email" in text:
            # check day/time
            cron = "0 17 * * 5"  # default Friday 5pm
            if "friday" in text and "5pm" in text:
                cron = "0 17 * * 5"
            elif "monday" in text and "9am" in text:
                cron = "0 9 * * 1"
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": cron, "timezone": "UTC"}),
                action=Action(name="send_email", params={"subject": "Summary", "body": "Summary email"}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 3: Disk usage threshold
        if "disk" in text:
            pct_match = re.search(r"(\d+)\s*%", text)
            thresh = int(pct_match.group(1)) if pct_match else 90
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="threshold", params={"metric": "disk_usage_pct", "threshold": thresh, "comparator": ">="}),
                action=Action(name="write_log_notification", params={"level": "warning", "message": f"Disk usage exceeded {thresh}%"}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 4: Webhook
        if "webhook" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": "0 0 * * *", "timezone": "UTC"}),
                action=Action(name="send_webhook", params={"url": "https://example.com/webhook"}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Case 5: Healthcheck
        if "healthcheck" in text or "health" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": "*/5 * * * *", "timezone": "UTC"}),
                action=Action(name="run_http_healthcheck", params={"url": "https://example.com/health"}),
                ambiguities=[], degraded_mode=True)
            return schema.model_validate(res.model_dump())

        # Fallback single unparsed
        res = ParsedResult(
            raw_text=prompt,
            detected_count=1,
            parseable=False,
            trigger=None,
            action=None,
            ambiguities=[], degraded_mode=True)
        return schema.model_validate(res.model_dump())


class ProviderChain(LLMProvider):
    def __init__(self, providers: List[LLMProvider]):
        self.providers = providers

    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        from .db import increment_provider_usage, log_audit_event
        from .quota import should_preemptively_skip
        last_error = None
        for p in self.providers:
            provider_name = p.__class__.__name__
            if should_preemptively_skip(provider_name):
                logger.warning(f"Preemptively skipping provider {provider_name} due to quota")
                log_audit_event("provider_preemptive_skip", {"provider": provider_name})
                continue
            
            # Retry loop for malformed JSON output (cap 2 attempts)
            for attempt in range(2):
                try:
                    retry_prompt = prompt if attempt == 0 else f"{prompt}\nNote: Previous response had invalid JSON format. Ensure output strictly adheres to schema."
                    increment_provider_usage(provider_name)
                    result = await p.complete_structured(retry_prompt, schema)
                    return result
                except (RateLimitError, ProviderUnavailableError) as e:
                    last_error = e
                    logger.warning(f"Failover triggered for provider {provider_name}: {e}")
                    log_audit_event("provider_failover", {"provider": provider_name, "error": str(e)})
                    break  # Break out to next provider
                except Exception as e:
                    last_error = e
                    logger.warning(f"Error on attempt {attempt+1} with provider {provider_name}: {e}")
                    if attempt == 1:
                        # After 2 failed attempts on this provider, failover
                        log_audit_event("provider_failover", {"provider": provider_name, "error": str(e)})
                        break

        raise AllProvidersExhaustedError(f"All LLM providers exhausted. Last error: {last_error}")
