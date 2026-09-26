from fastapi import FastAPI, Header, Query
from typing import Optional
from shared.logging_config import setup_logging_and_middleware
from shared.schemas.plan import AutomationPlan
from .classifier import classify_plan, ClassificationResult
from .ethics_agent import router as ethics_router

app = FastAPI(title="Guardrail Service", version="1.0.0")
setup_logging_and_middleware(app, "guardrail")
app.include_router(ethics_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "guardrail"}


@app.post("/classify", response_model=ClassificationResult)
async def classify_automation_plan(
    plan: AutomationPlan,
    force_groq_fail: bool = Query(False, description="Simulate Groq endpoint unreachable for fail-closed test")
):
    result = await classify_plan(plan, force_groq_fail=force_groq_fail)
    return result
