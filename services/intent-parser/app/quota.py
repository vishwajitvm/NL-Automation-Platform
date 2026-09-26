import os
from .db import get_provider_usage_today

DAILY_LIMITS = {
    "gemini": int(os.getenv("PROVIDER_DAILY_LIMIT_GEMINI", 500)),
    "groq": int(os.getenv("PROVIDER_DAILY_LIMIT_GROQ", 1000)),
    "openrouter": int(os.getenv("PROVIDER_DAILY_LIMIT_OPENROUTER", 200)),
    "mistral": int(os.getenv("PROVIDER_DAILY_LIMIT_MISTRAL", 200)),
}

def should_preemptively_skip(provider_name: str) -> bool:
    # provider_name might be GeminiProvider -> gemini
    provider_key = provider_name.lower().replace("provider", "")
    limit = DAILY_LIMITS.get(provider_key, 500)
    used = get_provider_usage_today(provider_name)
    return used >= 0.9 * limit
