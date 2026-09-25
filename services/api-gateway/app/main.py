from datetime import datetime, timezone, timedelta
import logging
import os
from typing import Any, Dict, List, Optional, Union
import httpx
from fastapi import FastAPI, HTTPException, status, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shared.logging_config import setup_logging_and_middleware
from shared.schemas.plan import AutomationPlan
from shared.safety.denylist import is_forbidden, FORBIDDEN_REFUSAL_MESSAGE
from .db import (
    list_automations,
    get_automation_by_id,
    archive_automation,
    get_audit_logs,
    create_host_agent_token,
    register_host_agent,
    record_host_agent_metric,
    get_next_host_agent_job,
    complete_host_agent_job,
    list_host_agents,
)

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
    user_response: Union[str, Dict[str, Any]] = Field(..., description="Response to ambiguity question or confirmation payload")


class RegisterAgentRequest(BaseModel):
    token: str
    os_family: str
    distro_id: Optional[str] = None
    distro_name: Optional[str] = None
    distro_version: Optional[str] = None
    package_manager: Optional[str] = None
    init_system: Optional[str] = None
    trash_path: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)


class AgentMetricRequest(BaseModel):
    metric: str
    value: float


class JobResultRequest(BaseModel):
    status: str
    result: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/host-agents/tokens")
def generate_agent_token():
    token, agent_id = create_host_agent_token()
    logger.info(f"Generated new host agent token for agent_id={agent_id}", extra={"extra_data": {"agent_id": agent_id}})
    return {
        "token": token,
        "agent_id": agent_id,
        "run_command": f"python -m host_agent run --token {token} --server http://localhost:8080"
    }


@app.post("/api/v1/host-agents/register")
def register_agent(req: RegisterAgentRequest):
    logger.info(
        f"Host agent registration request: os={req.os_family}, distro={req.distro_name} {req.distro_version}, capabilities={req.capabilities}",
        extra={"extra_data": {"os_family": req.os_family, "distro": req.distro_name, "caps": req.capabilities}}
    )
    agent = register_host_agent(
        token=req.token,
        os_family=req.os_family,
        distro_id=req.distro_id,
        distro_name=req.distro_name,
        distro_version=req.distro_version,
        package_manager=req.package_manager,
        init_system=req.init_system,
        trash_path=req.trash_path,
        capabilities=req.capabilities
    )
    if not agent:
        logger.warning(f"Unauthorized registration attempt with token prefix '{req.token[:8]}...'")
        raise HTTPException(status_code=401, detail="Invalid host agent registration token.")
    logger.info(f"Host agent successfully registered: agent_id={agent.get('id')}, os={agent.get('os_family')}")
    return {"status": "online", "agent": agent}


@app.post("/api/v1/host-agents/metrics")
def post_agent_metric(req: AgentMetricRequest, x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token")):
    if not x_agent_token:
        logger.warning("Agent metric push rejected: Missing X-Agent-Token header")
        raise HTTPException(status_code=401, detail="Missing X-Agent-Token header")
    recorded = record_host_agent_metric(x_agent_token, req.metric, req.value)
    if not recorded:
        logger.warning("Agent metric push rejected: Invalid host agent token")
        raise HTTPException(status_code=401, detail="Invalid host agent token")
    logger.debug(f"Recorded host agent metric: {req.metric}={req.value}", extra={"extra_data": {"metric": req.metric, "val": req.value}})
    return {"status": "recorded", "metric": req.metric, "value": req.value}


@app.get("/api/v1/host-agents/jobs/next")
def poll_agent_job(x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token")):
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Token header")
    job = get_next_host_agent_job(x_agent_token)
    if job:
        logger.info(f"Dispatched pending job {job.get('id')} ({job.get('action_name')}) to host agent")
    else:
        logger.debug("Host agent job poll: no pending jobs")
    return {"job": job}


@app.post("/api/v1/host-agents/jobs/{job_id}/result")
def submit_agent_job_result(job_id: str, req: JobResultRequest, x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token")):
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Token header")
    logger.info(f"Host agent returned result for job {job_id}: status={req.status}", extra={"extra_data": {"job_id": job_id, "status": req.status, "result": req.result}})
    success = complete_host_agent_job(x_agent_token, job_id, req.status, req.result)
    if not success:
        logger.error(f"Failed to record result for job {job_id}: unauthorized or not found")
        raise HTTPException(status_code=404, detail="Job not found or unauthorized")
    return {"status": "acknowledged", "job_id": job_id}


@app.get("/api/v1/host-agents")
def get_host_agents():
    agents = list_host_agents()
    return {"agents": agents, "host_agents": agents}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/api/v1/automations")
def get_automations(status: Optional[str] = Query(None)):
    items = list_automations(status=status)
    return {"automations": items}


@app.get("/api/v1/automations/{automation_id}")
def get_automation(automation_id: str):
    auto = get_automation_by_id(automation_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found")
    return auto


@app.delete("/api/v1/automations/{automation_id}")
async def delete_automation(automation_id: str):
    success = archive_automation(automation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Automation not found")

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.delete(f"{TRIGGER_ENGINE_URL}/triggers/{automation_id}")
    except Exception as e:
        logger.warning(f"Could not unregister trigger for {automation_id}: {e}")

    return {"status": "archived", "id": automation_id}


@app.get("/api/v1/automations/{automation_id}/audit")
def get_automation_audit(automation_id: str, limit: int = 50):
    logs = get_audit_logs(automation_id=automation_id, limit=limit)
    return {"audit_logs": logs}


@app.get("/api/v1/audit")
def get_all_audit(limit: int = 50):
    logs = get_audit_logs(limit=limit)
    return {"audit_logs": logs}


@app.post("/api/v1/automations", status_code=status.HTTP_201_CREATED)
async def create_automation(req: CreateAutomationRequest):
    raw_text = req.text.strip()
    if not raw_text:
        logger.warning("Empty automation request received")
        raise HTTPException(status_code=400, detail="I couldn't understand that.")

    logger.info(f"Processing automation request: '{raw_text}' (tz={req.timezone})", extra={"extra_data": {"raw_text": raw_text, "tz": req.timezone}})

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 0. Request Router Pre-Gate
        try:
            logger.debug(f"Querying Request Router for text: '{raw_text}'")
            route_resp = await client.post(
                f"{INTENT_PARSER_URL}/route",
                json={"raw_text": raw_text}
            )
            if route_resp.status_code == 200:
                route_data = route_resp.json()
                logger.info(f"Request Router classification: lane='{route_data.get('lane')}' (reason='{route_data.get('reason')}')")
                if route_data.get("lane") == "disallowed_content":
                    logger.warning(f"Request blocked by content policy: reason={route_data.get('reason')}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "content_policy_blocked",
                            "message": route_data.get("refusal", "Request violates content policy."),
                            "reason": route_data.get("reason"),
                        }
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Request router note: {e}")

        # 1. Intent Parser Call
        try:
            logger.debug("Dispatching request to Intent Parser")
            parse_resp = await client.post(
                f"{INTENT_PARSER_URL}/parse",
                json={"raw_text": raw_text}
            )
        except Exception as e:
            logger.error(f"Intent parser connection error: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail="Intent parser service unavailable")

        if parse_resp.status_code == 422:
            err_data = parse_resp.json()
            logger.warning(f"Compound automation rejected: {err_data.get('detected_count', 0)} tasks detected")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=err_data.get("message", "Please describe one automation at a time.")
            )

        if parse_resp.status_code != 200:
            logger.error(f"Intent Parser failed with status {parse_resp.status_code}")
            raise HTTPException(status_code=parse_resp.status_code, detail="Failed to parse automation request")

        plan_data = parse_resp.json()
        action_name = (plan_data.get("action") or {}).get("name")
        trigger_type = (plan_data.get("trigger") or {}).get("type")
        logger.debug(
            f"Parsed plan: action={action_name}, trigger={trigger_type}, parseable={plan_data.get('parseable')}",
            extra={"extra_data": {"plan": plan_data}}
        )

        # Hard denylist check before confirmation modals are even offered
        action_obj = plan_data.get("action") or {}
        if action_obj.get("name") == "delete_path":
            target_path = action_obj.get("params", {}).get("path", "")
            if is_forbidden(target_path):
                logger.warning(f"Hard denylist violation intercepted: '{target_path}'")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "FORBIDDEN_DELETION",
                        "message": FORBIDDEN_REFUSAL_MESSAGE,
                        "path": target_path
                    }
                )

        if req.timezone and plan_data.get("trigger") and "params" in plan_data["trigger"]:
            if "timezone" not in plan_data["trigger"]["params"]:
                plan_data["trigger"]["params"]["timezone"] = req.timezone

        # 2. Guardrail Safety Check
        try:
            logger.debug("Dispatching plan to Security Guardrail Pre-Gate")
            guard_resp = await client.post(
                f"{GUARDRAIL_URL}/classify",
                json=plan_data
            )
        except Exception as e:
            logger.error(f"Guardrail service connection error: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail="Security guardrail service unavailable (fail-closed)")

        if guard_resp.status_code != 200:
            logger.error(f"Security classification failed with status {guard_resp.status_code}")
            raise HTTPException(status_code=guard_resp.status_code, detail="Security classification failed")

        guard_data = guard_resp.json()
        logger.info(f"Guardrail disposition: decision='{guard_data.get('decision')}', categories={guard_data.get('categories')}")
        if guard_data.get("decision") == "blocked":
            logger.warning(f"Plan blocked by guardrails: categories={guard_data.get('categories')}, reason={guard_data.get('reason')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "GUARDRAIL_BLOCKED",
                    "reason": guard_data.get("reason", "Violated security guardrails policy."),
                    "categories": guard_data.get("categories", []),
                    "suggested_alternative": "You can clean temporary files and cache or monitor disk usage instead."
                }
            )

        if not plan_data.get("parseable", True):
            logger.warning(f"Unparseable plan rejected for text: '{raw_text}'")
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
                logger.info(f"Identified duplicate active automation: id={item.get('id')}")
                break

        # 4. Decision Agent Resolution
        try:
            logger.debug("Invoking LangGraph Decision Agent")
            decision_resp = await client.post(
                f"{DECISION_AGENT_URL}/resolve",
                json={"plan": plan_data}
            )
        except Exception as e:
            logger.error(f"Decision agent connection error: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail="Decision agent service unavailable")

        if decision_resp.status_code != 200:
            logger.error(f"Decision agent returned HTTP {decision_resp.status_code}")
            raise HTTPException(status_code=decision_resp.status_code, detail="Decision agent resolution failed")

        decision_data = decision_resp.json()
        logger.info(f"Decision Agent resolved automation: id={decision_data.get('automation_id')}, status={decision_data.get('status')}")

        if decision_data.get("status") == "draft":
            logger.info(f"Automation paused in draft: prompt='{decision_data.get('clarification_question')}'")
            return {
                "id": decision_data["automation_id"],
                "status": "draft",
                "confirmation_required": decision_data.get("confirmation_required", False),
                "risk_tier": decision_data.get("risk_tier"),
                "preview": decision_data.get("preview"),
                "clarification_prompt": decision_data.get("clarification_question"),
                "plan": plan_data,
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            }

        logger.info(f"Automation successfully activated: id={decision_data['automation_id']}")
        return {
            "id": decision_data["automation_id"],
            "status": "active",
            "plan": decision_data.get("plan", plan_data),
            "created_at": datetime.now(timezone.utc).isoformat()
        }


@app.post("/api/v1/commands")
async def execute_immediate_command(req: CreateAutomationRequest):
    """Executes a one-off immediate command (trigger.type = 'immediate')"""
    raw_text = req.text.strip()
    if not raw_text:
        logger.warning("Empty immediate command received")
        raise HTTPException(status_code=400, detail="I couldn't understand that.")

    logger.info(f"Processing immediate command: '{raw_text}'", extra={"extra_data": {"command": raw_text}})

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Route
        logger.debug(f"Routing immediate command: '{raw_text}'")
        route_resp = await client.post(f"{INTENT_PARSER_URL}/route", json={"raw_text": raw_text})
        if route_resp.status_code == 200:
            route_data = route_resp.json()
            logger.info(f"Immediate command lane: '{route_data.get('lane')}' (reason='{route_data.get('reason')}')")
            if route_data.get("lane") == "disallowed_content":
                logger.warning(f"Immediate command blocked by content policy: reason={route_data.get('reason')}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "content_policy_blocked",
                        "message": route_data.get("refusal", "Request violates content policy."),
                        "reason": route_data.get("reason"),
                    }
                )

        # Parse
        logger.debug("Parsing immediate command into structured plan")
        parse_resp = await client.post(f"{INTENT_PARSER_URL}/parse", json={"raw_text": raw_text})
        if parse_resp.status_code != 200:
            logger.error(f"Failed to parse immediate command: status={parse_resp.status_code}")
            raise HTTPException(status_code=parse_resp.status_code, detail="Failed to parse command request")

        plan_data = parse_resp.json()
        if not plan_data.get("parseable", True):
            logger.warning(f"Immediate command is unparseable: '{raw_text}'")
            raise HTTPException(status_code=400, detail="I couldn't understand that.")

        # Ensure immediate trigger
        plan_data["trigger"] = {"type": "immediate", "params": {}}

        # Hard denylist check before anything else
        action_obj = plan_data.get("action") or {}
        if action_obj.get("name") == "delete_path":
            target_path = action_obj.get("params", {}).get("path", "")
            if is_forbidden(target_path):
                logger.warning(f"Immediate command hard denylist violation: '{target_path}'")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "FORBIDDEN_DELETION",
                        "message": FORBIDDEN_REFUSAL_MESSAGE,
                        "path": target_path
                    }
                )

        # Guardrail check
        logger.debug("Executing Guardrail check for immediate command")
        guard_resp = await client.post(f"{GUARDRAIL_URL}/classify", json=plan_data)
        if guard_resp.status_code == 200:
            guard_data = guard_resp.json()
            logger.info(f"Immediate command guardrail check: decision='{guard_data.get('decision')}'")
            if guard_data.get("decision") == "blocked":
                logger.warning(f"Immediate command blocked by guardrails: categories={guard_data.get('categories')}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "GUARDRAIL_BLOCKED",
                        "reason": guard_data.get("reason", "Violated security guardrails policy."),
                        "categories": guard_data.get("categories", [])
                    }
                )

        # Decision agent resolution
        logger.debug("Dispatching immediate command to LangGraph Decision Agent")
        decision_resp = await client.post(f"{DECISION_AGENT_URL}/resolve", json={"plan": plan_data})
        if decision_resp.status_code != 200:
            logger.error(f"Decision agent failed for immediate command: status={decision_resp.status_code}")
            raise HTTPException(status_code=decision_resp.status_code, detail="Failed to process command")

        decision_data = decision_resp.json()
        logger.info(f"Decision agent immediate command outcome: id={decision_data.get('automation_id')}, status={decision_data.get('status')}")
        if decision_data.get("status") == "draft":
            return {
                "id": decision_data["automation_id"],
                "status": "draft",
                "confirmation_required": decision_data.get("confirmation_required", False),
                "risk_tier": decision_data.get("risk_tier"),
                "preview": decision_data.get("preview"),
                "plan": plan_data
            }

        logger.info(f"Immediate command executed successfully: id={decision_data['automation_id']}")
        return {
            "id": decision_data["automation_id"],
            "status": "executed",
            "plan": plan_data,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }


@app.post("/api/v1/automations/{automation_id}/resume")
async def resume_automation(automation_id: str, req: ResumeAutomationRequest):
    """Resume an ambiguous automation or confirm destructive action currently in draft status"""
    logger.info(f"Resume request for automation {automation_id}: user_response={req.user_response}", extra={"extra_data": {"automation_id": automation_id, "user_response": req.user_response}})
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{DECISION_AGENT_URL}/resume",
                json={"automation_id": automation_id, "user_response": req.user_response}
            )
        except Exception as e:
            logger.error(f"Failed to communicate with decision agent on resume: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"Failed to communicate with decision agent: {e}")

        if resp.status_code != 200:
            logger.error(f"Decision agent resume failed: status={resp.status_code}, response={resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        logger.info(f"Automation {automation_id} successfully resumed with status '{data.get('status', 'active')}'")
        return {
            "id": automation_id,
            "status": data.get("status", "active"),
            "plan": data.get("plan"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
