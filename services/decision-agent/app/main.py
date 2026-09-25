import uuid
import logging
from typing import Any, Dict, Optional, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from shared.logging_config import setup_logging_and_middleware
from shared.schemas.plan import AutomationPlan
from .graph import decision_graph, DecisionState
from .db import sweep_expired_drafts

logger = logging.getLogger("decision-agent")

app = FastAPI(title="Decision Agent Service", version="1.0.0")
setup_logging_and_middleware(app, "decision-agent")


class ResolveRequest(BaseModel):
    plan: AutomationPlan
    automation_id: Optional[str] = None
    user_id: Optional[str] = None


class ResumeRequest(BaseModel):
    automation_id: str
    user_response: Union[str, Dict[str, Any]]


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "decision-agent"}


@app.post("/resolve")
async def resolve_plan(req: ResolveRequest):
    auto_id = req.automation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": auto_id}}
    
    initial_state: DecisionState = {
        "automation_id": auto_id,
        "user_id": req.user_id,
        "plan": req.plan.model_dump(),
        "clarification_question": None,
        "user_response": None,
        "final_trigger": None,
        "risk_tier": "low",
        "preview_data": None,
        "confirmation_payload": None,
        "status": "initial",
        "is_paused": False
    }

    # Run graph until interrupt or completion
    state_output = await decision_graph.ainvoke(initial_state, config=config)
    
    # Check if graph paused at interrupt
    snapshot = decision_graph.get_state(config)
    if snapshot.next:
        question = "Please clarify details"
        for task in snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                val = task.interrupts[0].value
                if isinstance(val, dict):
                    if val.get("type") == "destructive_confirmation_required":
                        return {
                            "automation_id": auto_id,
                            "status": "draft",
                            "confirmation_required": True,
                            "risk_tier": val.get("risk_tier"),
                            "preview": val.get("preview"),
                            "action": val.get("action"),
                            "paused_node": "await_confirmation"
                        }
                    question = val.get("question", question)

        return {
            "automation_id": auto_id,
            "status": "draft",
            "clarification_question": question,
            "paused_node": snapshot.next[0] if snapshot.next else "ask_user"
        }

    return {
        "automation_id": auto_id,
        "status": state_output.get("status", "active"),
        "final_trigger": state_output.get("final_trigger"),
        "plan": state_output.get("plan")
    }


@app.post("/resume")
async def resume_plan(req: ResumeRequest):
    config = {"configurable": {"thread_id": req.automation_id}}
    
    snapshot = decision_graph.get_state(config)
    if not snapshot.next:
        raise HTTPException(status_code=400, detail="Automation is not in an interrupted/waiting state.")

    # Resume graph with user response
    state_output = await decision_graph.ainvoke(
        Command(resume=req.user_response),
        config=config
    )

    # Check if another interrupt followed (e.g. ambiguity resolved then destructive confirmation needed)
    post_snapshot = decision_graph.get_state(config)
    if post_snapshot.next:
        for task in post_snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                val = task.interrupts[0].value
                if isinstance(val, dict) and val.get("type") == "destructive_confirmation_required":
                    return {
                        "automation_id": req.automation_id,
                        "status": "draft",
                        "confirmation_required": True,
                        "risk_tier": val.get("risk_tier"),
                        "preview": val.get("preview"),
                        "action": val.get("action"),
                        "paused_node": "await_confirmation"
                    }

    return {
        "automation_id": req.automation_id,
        "status": state_output.get("status", "active"),
        "final_trigger": state_output.get("final_trigger"),
        "plan": state_output.get("plan")
    }


@app.post("/sweeper/run")
def trigger_sweeper():
    archived = sweep_expired_drafts()
    return {"status": "ok", "archived_count": len(archived), "archived_ids": archived}
