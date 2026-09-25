from datetime import datetime, timezone, timedelta
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.logging_config import setup_logging_and_middleware
from shared.schemas.plan import AutomationPlan
from .db import list_automations, get_automation_by_id, archive_automation, get_audit_logs

logger = logging.getLogger("api-gateway")

app = FastAPI(title="NL-Automation API Gateway", version="1.0.0")
setup_logging_and_middleware(app, "api-gateway")

# CORS setup for Frontend Next.js app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INTENT_PARSER_URL = os.getenv("INTENT_PARSER_URL", "http://intent-parser:8000")
GUARDRAIL_URL = os.getenv("GUARDRAIL_URL", "http://guardrail:8000")
DECISION_AGENT_URL = os.getenv("DECISION_AGENT_URL", "http://decision-agent:8000")
TRIGGER_ENGINE_URL = os.getenv("TRIGGER_ENGINE_URL", "http://trigger-engine:8000")


class CreateAutomationRequest(BaseModel):
    text: str = Field(..., description="Plain-English description of the automation")
    timezone: str = Field("UTC", description="User local timezone")


class ResumeAutomationRequest(BaseModel):
    user_response: str = Field(..., description="Response to ambiguity question")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/api/v1/automations")
def get_automations(status: Optional[str] = Query(None)):
    """List automations filtered optionally by status"""
    items = list_automations(status=status)
    return {"automations": items}


@app.get("/api/v1/automations/{automation_id}")
def get_automation(automation_id: str):
    """Retrieve details of a single automation"""
    auto = get_automation_by_id(automation_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")
    return auto


@app.delete("/api/v1/automations/{automation_id}")
async def delete_automation(automation_id: str):
    """Archive an automation and unregister trigger"""
    success = archive_automation(automation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Automation not found")

    # Unregister from trigger engine
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.delete(f"{TRIGGER_ENGINE_URL}/triggers/{automation_id}")
    except Exception as e:
        logger.warning(f"Could not unregister trigger for {automation_id}: {e}")

    return {"status": "archived", "id": automation_id}


@app.get("/api/v1/automations/{automation_id}/audit")
def get_automation_audit(automation_id: str, limit: int = 50):
    """Get audit logs for a specific automation"""
    logs = get_audit_logs(automation_id=automation_id, limit=limit)
    return {"audit_logs": logs}


@app.get("/api/v1/audit")
def get_all_audit(limit: int = 50):
    """Get global audit logs"""
    logs = get_audit_logs(limit=limit)
    return {"audit_logs": logs}


@app.post("/api/v1/automations", status_code=status.HTTP_201_CREATED)
async def create_automation(req: CreateAutomationRequest):
    raw_text = req.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="I couldn't understand that.")

    # 1. Intent Parser Call
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            parse_resp = await client.post(
                f"{INTENT_PARSER_URL}/parse",
                json={"raw_text": raw_text}
            )
        except Exception as e:
            logger.error(f"Intent parser connection error: {e}")
            raise HTTPException(status_code=503, detail="Intent parser service unavailable")

        if parse_resp.status_code == 422:
            # Compound automation rejected
            err_data = parse_resp.json()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=err_data.get("message", "Please describe one automation at a time.")
            )

        if parse_resp.status_code != 200:
            raise HTTPException(status_code=parse_resp.status_code, detail="Failed to parse automation request")

        plan_data = parse_resp.json()

        # Ensure user timezone is incorporated
        if plan_data.get("trigger") and "params" in plan_data["trigger"]:
            if req.timezone and "timezone" not in plan_data["trigger"]["params"]:
                plan_data["trigger"]["params"]["timezone"] = req.timezone

        # 2. Guardrail Safety Check (evaluates plan including raw_text against destructive actions)
        try:
            guard_resp = await client.post(
                f"{GUARDRAIL_URL}/classify",
                json=plan_data
            )
        except Exception as e:
            logger.error(f"Guardrail service connection error: {e}")
            raise HTTPException(status_code=503, detail="Security guardrail service unavailable (fail-closed)")

        if guard_resp.status_code != 200:
            raise HTTPException(status_code=guard_resp.status_code, detail="Security classification failed")

        guard_data = guard_resp.json()
        if guard_data.get("decision") == "blocked":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "GUARDRAIL_BLOCKED",
                    "reason": guard_data.get("reason", "Violated security guardrails policy."),
                    "categories": guard_data.get("categories", []),
                    "suggested_alternative": "You can monitor disk usage with a webhook alert instead."
                }
            )

        if not plan_data.get("parseable", True):
            raise HTTPException(status_code=400, detail="I couldn't understand that.")

        # 3. Check for duplicate/conflicting active automation
        existing = list_automations(status="active")
        for item in existing:
            sp = item.get("structured_plan", {})
            if (
                sp.get("trigger", {}).get("type") == plan_data.get("trigger", {}).get("type") and
                sp.get("action", {}).get("name") == plan_data.get("action", {}).get("name") and
                sp.get("trigger", {}).get("params") == plan_data.get("trigger", {}).get("params")
            ):
                logger.info(f"Duplicate active automation detected with id {item.get('id')}")
                # We permit proceeding but warn or associate
                break

        # 4. Decision Agent Resolution
        try:
            decision_resp = await client.post(
                f"{DECISION_AGENT_URL}/resolve",
                json={"plan": plan_data}
            )
        except Exception as e:
            logger.error(f"Decision agent connection error: {e}")
            raise HTTPException(status_code=503, detail="Decision agent service unavailable")

        if decision_resp.status_code != 200:
            raise HTTPException(status_code=decision_resp.status_code, detail="Decision agent resolution failed")

        decision_data = decision_resp.json()

        # If status is draft (waiting for ambiguity answer)
        if decision_data.get("status") == "draft":
            return {
                "id": decision_data["automation_id"],
                "status": "draft",
                "clarification_prompt": decision_data.get("clarification_question"),
                "plan": plan_data,
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            }

        # Otherwise active
        return {
            "id": decision_data["automation_id"],
            "status": "active",
            "plan": decision_data.get("plan", plan_data),
            "created_at": datetime.now(timezone.utc).isoformat()
        }


@app.post("/api/v1/automations/{automation_id}/resume")
async def resume_automation(automation_id: str, req: ResumeAutomationRequest):
    """Resume an ambiguous automation currently in draft status"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{DECISION_AGENT_URL}/resume",
                json={"automation_id": automation_id, "user_response": req.user_response}
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to communicate with decision agent: {e}")

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        return {
            "id": automation_id,
            "status": "active",
            "plan": data.get("plan"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
