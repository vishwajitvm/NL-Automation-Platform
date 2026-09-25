import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shared.logging_config import setup_logging_and_middleware
from shared.schemas.plan import AutomationPlan
from .router import router as request_router
from .providers import (
    ProviderChain,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
    DeterministicRuleProvider,
    ParsedResult,
    AllProvidersExhaustedError,
)

logger = logging.getLogger("intent-parser")

app = FastAPI(title="Intent Parser Service", version="1.0.0")
setup_logging_and_middleware(app, "intent-parser")
app.include_router(request_router)

# Default Provider Chain: Gemini -> Groq -> OpenRouter -> DeterministicRuleFallback
chain = ProviderChain([
    GeminiProvider(),
    GroqProvider(),
    OpenRouterProvider(),
    DeterministicRuleProvider(),
])


class ParseRequest(BaseModel):
    raw_text: str = Field(..., description="Raw natural language automation description")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "intent-parser"}


@app.post("/parse", response_model=AutomationPlan)
async def parse_intent(req: ParseRequest):
    raw_text = req.raw_text.strip()
    if not raw_text:
        logger.debug("Received empty raw_text in intent parser, returning unparseable plan")
        return AutomationPlan(
            raw_text=req.raw_text,
            parseable=False,
            trigger=None,
            action=None,
            ambiguities=[]
        )

    logger.info(f"Parsing natural language intent: '{raw_text}'", extra={"extra_data": {"length": len(raw_text), "raw_text": raw_text}})

    try:
        parsed: ParsedResult = await chain.complete_structured(raw_text, ParsedResult)
        logger.debug(f"LLM parsing completed: detected_count={parsed.detected_count}, parseable={parsed.parseable}")
    except AllProvidersExhaustedError as e:
        logger.error(f"All LLM providers exhausted during intent parsing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intent Parser service unavailable: all LLM providers failed."
        )

    # 1. Compound automation check
    if parsed.detected_count >= 2:
        logger.warning(f"Rejected compound automation (count={parsed.detected_count}): '{raw_text}'")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "compound_automation_rejected",
                "message": "Please describe one automation at a time.",
                "detected_count": parsed.detected_count
            }
        )

    # 2. Unparseable / gibberish check
    if not parsed.parseable:
        logger.warning(f"Unparseable intent detected for input: '{raw_text}'")
        return AutomationPlan(
            raw_text=raw_text,
            parseable=False,
            trigger=None,
            action=None,
            ambiguities=[]
        )

    action_name = parsed.action.name if parsed.action else None
    trigger_type = parsed.trigger.type if parsed.trigger else None
    logger.info(
        f"Intent parsed successfully: action='{action_name}', trigger='{trigger_type}', ambiguities={len(parsed.ambiguities)}",
        extra={"extra_data": {"action": action_name, "trigger": trigger_type, "ambiguities": parsed.ambiguities}}
    )

    # 3. Successful parse
    return AutomationPlan(
        raw_text=raw_text,
        trigger=parsed.trigger,
        action=parsed.action,
        ambiguities=parsed.ambiguities,
        parseable=True
    )
