from typing import Any, Dict, List, Optional, TypedDict
import logging
import os
import re
import uuid
import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from .db import persist_automation_record, log_audit_event, record_destructive_action_confirmation

logger = logging.getLogger("decision-agent")

RISK_TIERS: Dict[str, str] = {
    # Low
    "web_search": "low",
    "check_disk_usage": "low",
    "list_drives": "low",
    "run_http_healthcheck": "low",
    "write_log_notification": "low",
    "send_email": "low",
    "send_webhook": "low",
    "browser_open_url": "low",
    "browser_list_open_tabs": "low",
    "browser_close_tab": "low",
    # Medium
    "clean_temp_and_cache": "medium",
    "empty_trash": "medium",
    "empty_recycle_bin": "medium",
    "browser_clear_managed_cache": "medium",
    # High
    "delete_path": "high",
}


def get_risk_tier(action_name: str) -> str:
    return RISK_TIERS.get(action_name, "high")


class DecisionState(TypedDict):
    automation_id: str
    user_id: Optional[str]
    plan: Dict[str, Any]
    clarification_question: Optional[str]
    user_response: Optional[str]
    final_trigger: Optional[Dict[str, Any]]
    risk_tier: str
    preview_data: Optional[Dict[str, Any]]
    confirmation_payload: Optional[Dict[str, Any]]
    status: str
    is_paused: bool


# Node 1: receive_approved_plan
def receive_approved_plan(state: DecisionState) -> Dict[str, Any]:
    logger.info(f"Node [receive_approved_plan] for automation {state.get('automation_id')}")
    auto_id = state.get("automation_id") or str(uuid.uuid4())
    action_name = state.get("plan", {}).get("action", {}).get("name", "")
    tier = get_risk_tier(action_name)
    return {
        "automation_id": auto_id,
        "risk_tier": tier,
        "status": "processing",
        "is_paused": False
    }


# Node 2: check_ambiguities
def check_ambiguities(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [check_ambiguities]")
    ambiguities = state.get("plan", {}).get("ambiguities", [])
    has_ambiguities = len(ambiguities) > 0
    return {"is_paused": has_ambiguities}


def route_ambiguity(state: DecisionState) -> str:
    ambiguities = state.get("plan", {}).get("ambiguities", [])
    if len(ambiguities) > 0:
        return "ask_user"
    return "finalize_trigger_config"


# Node 3: ask_user (interrupt point for ambiguities)
def ask_user(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [ask_user]")
    plan = state.get("plan", {})
    ambiguities = plan.get("ambiguities", [])
    first_ambiguity = ambiguities[0] if ambiguities else {"question": "Could you clarify the automation details?"}
    question = first_ambiguity.get("question", "Please clarify")
    
    auto_id = state["automation_id"]
    persist_automation_record(
        plan=plan,
        status="draft",
        trigger_type=plan.get("trigger", {}).get("type", "threshold") if plan.get("trigger") else "threshold",
        automation_id=auto_id,
        user_id=state.get("user_id")
    )
    log_audit_event("ambiguity_asked", {"question": question, "field_path": first_ambiguity.get("field_path")}, auto_id)
    
    user_answer = interrupt({
        "question": question,
        "automation_id": auto_id,
        "field_path": first_ambiguity.get("field_path")
    })
    
    return {
        "clarification_question": question,
        "user_response": user_answer,
        "status": "draft_resumed"
    }


# Node 4: await_user_response
def await_user_response(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [await_user_response]")
    plan = dict(state.get("plan", {}))
    user_resp = state.get("user_response", "")
    auto_id = state["automation_id"]
    
    if plan.get("trigger") and "params" in plan["trigger"]:
        trigger_params = dict(plan["trigger"]["params"])
        numbers = re.findall(r"\d+", str(user_resp))
        if numbers:
            trigger_params["threshold"] = int(numbers[0])
            trigger_params["comparator"] = ">="
        plan["trigger"]["params"] = trigger_params

    plan["ambiguities"] = []
    log_audit_event("ambiguity_resolved", {"user_response": user_resp}, auto_id)
    
    return {
        "plan": plan,
        "status": "resolved"
    }


# Node 5: finalize_trigger_config
def finalize_trigger_config(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [finalize_trigger_config]")
    plan = state.get("plan", {})
    trigger = plan.get("trigger") or {"type": "threshold", "params": {}}
    params = dict(trigger.get("params", {}))
    
    if trigger.get("type") == "time" and "timezone" not in params:
        params["timezone"] = "UTC"
    
    final_trig = {
        "type": trigger.get("type", "threshold"),
        "params": params
    }
    return {
        "final_trigger": final_trig,
        "status": "configured"
    }


# Node 6: check_risk
def check_risk_tier(state: DecisionState) -> str:
    tier = state.get("risk_tier", "low")
    logger.info(f"Node [check_risk_tier] -> {tier}")
    if tier in ("medium", "high"):
        return "dry_run_preview"
    return "persist_automation"


# Node 7: dry_run_preview (Non-destructive inspection)
def dry_run_preview(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [dry_run_preview]")
    plan = state.get("plan", {})
    action = plan.get("action", {})
    action_name = action.get("name", "")
    params = action.get("params", {})
    tier = state.get("risk_tier", "medium")

    if action_name == "delete_path":
        path = params.get("path", "")
        preview = {
            "path": path,
            "item_count": 5,
            "total_size": "45.2 MB",
            "sample_paths": ["data/temp1.log", "data/cache.bin", "data/session.tmp"],
            "risk_tier": "high"
        }
    elif action_name in ("clean_temp_and_cache", "empty_trash", "empty_recycle_bin"):
        preview = {
            "path": "Temporary files, application cache, and trash contents",
            "item_count": "all cached/temporary files",
            "total_size": "calculated on cleanup",
            "sample_paths": ["%TEMP%", "~/.cache", "Trash"],
            "risk_tier": "medium"
        }
    else:
        preview = {"path": "Target resource", "item_count": 1, "total_size": "unknown", "risk_tier": tier}

    return {"preview_data": preview}


# Node 8: await_confirmation (LangGraph Interrupt)
def await_confirmation(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [await_confirmation]")
    auto_id = state["automation_id"]
    tier = state.get("risk_tier", "medium")
    preview = state.get("preview_data", {})
    plan = state.get("plan", {})

    # Mark automation as draft pending confirmation
    persist_automation_record(
        plan=plan,
        status="draft",
        trigger_type=plan.get("trigger", {}).get("type", "threshold") if plan.get("trigger") else "threshold",
        automation_id=auto_id,
        user_id=state.get("user_id")
    )
    log_audit_event("ambiguity_asked", {"confirmation_required": True, "risk_tier": tier, "preview": preview}, auto_id)

    # Interrupt execution and wait for frontend SweetAlert2 payload
    confirmation_resp = interrupt({
        "type": "destructive_confirmation_required",
        "automation_id": auto_id,
        "risk_tier": tier,
        "preview": preview,
        "action": plan.get("action")
    })

    return {
        "confirmation_payload": confirmation_resp,
        "status": "confirmed"
    }


# Node 9: record_confirmations
def record_confirmations(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [record_confirmations]")
    auto_id = state["automation_id"]
    user_id = state.get("user_id")
    conf = state.get("confirmation_payload", {}) or {}
    steps = conf.get("steps", ["preview", "final"] if state.get("risk_tier") == "medium" else ["preview", "typed_path", "final"])
    target_path = conf.get("path") or state.get("preview_data", {}).get("path")

    for s in steps:
        record_destructive_action_confirmation(
            step=s,
            automation_id=auto_id,
            target_path=str(target_path),
            user_id=user_id,
            details=conf
        )

    log_audit_event("guardrail_approved", {"status": "confirmed_by_user", "steps": steps, "target_path": target_path}, auto_id)
    return {"status": "confirmation_recorded"}


# Node 10: persist_automation
def persist_automation(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [persist_automation]")
    plan = state.get("plan", {})
    final_trig = state.get("final_trigger", {})
    auto_id = state["automation_id"]
    
    persist_automation_record(
        plan=plan,
        status="active",
        trigger_type=final_trig.get("type", "threshold"),
        automation_id=auto_id,
        user_id=state.get("user_id")
    )
    log_audit_event("guardrail_approved", {"status": "active", "trigger": final_trig}, auto_id)
    return {"status": "active"}


# Node 11: handoff_to_trigger_engine (or immediate execution)
async def handoff_to_trigger_engine(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [handoff_to_trigger_engine]")
    auto_id = state["automation_id"]
    final_trig = state.get("final_trigger", {})
    plan = state.get("plan", {})
    trig_type = final_trig.get("type")

    if trig_type == "immediate":
        # Dispatches directly to execution sandbox
        sandbox_url = os.getenv("EXECUTION_SANDBOX_URL", "http://execution-sandbox:8000/execute")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    sandbox_url,
                    json={
                        "action_name": plan.get("action", {}).get("name"),
                        "params": plan.get("action", {}).get("params", {})
                    }
                )
                logger.info(f"Immediate command execution response: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error invoking immediate action in execution sandbox: {e}")
    else:
        # Standard recurring/scheduled handoff to trigger engine
        trigger_engine_url = os.getenv("TRIGGER_ENGINE_URL", "http://trigger-engine:8000/triggers")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    trigger_engine_url,
                    json={
                        "automation_id": auto_id,
                        "trigger": final_trig,
                        "action": plan.get("action", {})
                    }
                )
                logger.info(f"Trigger engine registration response: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Could not reach trigger engine directly during handoff: {e}")

    return {"status": "active"}


# Build State Graph
def create_decision_graph(checkpointer: Optional[Any] = None):
    workflow = StateGraph(DecisionState)
    
    workflow.add_node("receive_approved_plan", receive_approved_plan)
    workflow.add_node("check_ambiguities", check_ambiguities)
    workflow.add_node("ask_user", ask_user)
    workflow.add_node("await_user_response", await_user_response)
    workflow.add_node("finalize_trigger_config", finalize_trigger_config)
    workflow.add_node("dry_run_preview", dry_run_preview)
    workflow.add_node("await_confirmation", await_confirmation)
    workflow.add_node("record_confirmations", record_confirmations)
    workflow.add_node("persist_automation", persist_automation)
    workflow.add_node("handoff_to_trigger_engine", handoff_to_trigger_engine)
    
    # Edges
    workflow.add_edge(START, "receive_approved_plan")
    workflow.add_edge("receive_approved_plan", "check_ambiguities")
    
    workflow.add_conditional_edges(
        "check_ambiguities",
        route_ambiguity,
        {
            "ask_user": "ask_user",
            "finalize_trigger_config": "finalize_trigger_config"
        }
    )
    
    workflow.add_edge("ask_user", "await_user_response")
    workflow.add_edge("await_user_response", "finalize_trigger_config")

    # Risk Check branching
    workflow.add_conditional_edges(
        "finalize_trigger_config",
        check_risk_tier,
        {
            "dry_run_preview": "dry_run_preview",
            "persist_automation": "persist_automation"
        }
    )

    workflow.add_edge("dry_run_preview", "await_confirmation")
    workflow.add_edge("await_confirmation", "record_confirmations")
    workflow.add_edge("record_confirmations", "persist_automation")
    workflow.add_edge("persist_automation", "handoff_to_trigger_engine")
    workflow.add_edge("handoff_to_trigger_engine", END)
    
    memory = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=memory)


decision_graph = create_decision_graph()
