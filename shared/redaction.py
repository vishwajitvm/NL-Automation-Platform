import re
from typing import Any, Dict, List, Union

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),
    re.compile(r"gsk_[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),
    re.compile(r"AQ\.[a-zA-Z0-9_\-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{16,}", re.IGNORECASE),
]

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "gemini_api_key",
    "groq_api_key",
    "openrouter_api_key",
    "mistral_api_key",
    "langsmith_api_key",
}


def redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def redact_data(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_string(obj)
    elif isinstance(obj, dict):
        return {
            k: "[REDACTED_SECRET]" if k.lower() in SENSITIVE_KEYS else redact_data(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [redact_data(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(redact_data(item) for item in obj)
    return obj
