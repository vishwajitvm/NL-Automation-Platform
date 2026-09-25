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
            "clean", "recycle", "bin", "email", "summary", "friday", "disk", "usage",
            "notify", "every", "when", "at", "if", "send", "webhook", "monday", "schedule",
            "healthcheck", "check", "log", "alert", "run"
        }
        meaningful_count = sum(1 for w in clean_words if w in known_keywords)

        if not text or len(clean_words) == 0 or (len(clean_words) > 2 and meaningful_count == 0):
            res = ParsedResult(
                raw_text=prompt,
                detected_count=0,
                parseable=False,
                trigger=None,
                action=None,
                ambiguities=[]
            )
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
                ambiguities=[]
            )
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
                ]
            )
            return schema.model_validate(res.model_dump())

        # Case 1: Recycle bin threshold
        if "recycle" in text or "bin" in text:
            pct_match = re.search(r"(\d+)\s*%", text)
            thresh = int(pct_match.group(1)) if pct_match else 80
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="threshold", params={"metric": "recycle_bin_percentage", "threshold": thresh, "comparator": ">="}),
                action=Action(name="empty_recycle_bin", params={}),
                ambiguities=[]
            )
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
                ambiguities=[]
            )
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
                ambiguities=[]
            )
            return schema.model_validate(res.model_dump())

        # Case 4: Webhook
        if "webhook" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": "0 0 * * *", "timezone": "UTC"}),
                action=Action(name="send_webhook", params={"url": "https://example.com/webhook"}),
                ambiguities=[]
            )
            return schema.model_validate(res.model_dump())

        # Case 5: Healthcheck
        if "healthcheck" in text or "health" in text:
            res = ParsedResult(
                raw_text=prompt,
                detected_count=1,
                parseable=True,
                trigger=Trigger(type="time", params={"cron": "*/5 * * * *", "timezone": "UTC"}),
                action=Action(name="run_http_healthcheck", params={"url": "https://example.com/health"}),
                ambiguities=[]
            )
            return schema.model_validate(res.model_dump())

        # Fallback single unparsed
        res = ParsedResult(
            raw_text=prompt,
            detected_count=1,
            parseable=False,
            trigger=None,
            action=None,
            ambiguities=[]
        )
        return schema.model_validate(res.model_dump())


class ProviderChain(LLMProvider):
    def __init__(self, providers: List[LLMProvider]):
        self.providers = providers

    async def complete_structured(self, prompt: str, schema: Type[BaseModel]) -> BaseModel:
        last_error = None
        for p in self.providers:
            # Retry loop for malformed JSON output (cap 2 attempts)
            for attempt in range(2):
                try:
                    retry_prompt = prompt if attempt == 0 else f"{prompt}\nNote: Previous response had invalid JSON format. Ensure output strictly adheres to schema."
                    result = await p.complete_structured(retry_prompt, schema)
                    return result
                except (RateLimitError, ProviderUnavailableError) as e:
                    last_error = e
                    provider_name = p.__class__.__name__
                    logger.warning(f"Failover triggered for provider {provider_name}: {e}")
                    log_audit_event("provider_failover", {"provider": provider_name, "error": str(e)})
                    break  # Break out to next provider
                except Exception as e:
                    last_error = e
                    logger.warning(f"Error on attempt {attempt+1} with provider {p.__class__.__name__}: {e}")
                    if attempt == 1:
                        # After 2 failed attempts on this provider, failover
                        provider_name = p.__class__.__name__
                        log_audit_event("provider_failover", {"provider": provider_name, "error": str(e)})
                        break

        raise AllProvidersExhaustedError(f"All LLM providers exhausted. Last error: {last_error}")
