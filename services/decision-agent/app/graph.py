from typing import Any, Dict, List, Optional, TypedDict
import logging
import os
import re
import uuid
import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from .db import persist_automation_record, log_audit_event

logger = logging.getLogger("decision-agent")


class DecisionState(TypedDict):
    automation_id: str
    user_id: Optional[str]
    plan: Dict[str, Any]
    clarification_question: Optional[str]
    user_response: Optional[str]
    final_trigger: Optional[Dict[str, Any]]
    status: str
    is_paused: bool


# Node 1: receive_approved_plan
def receive_approved_plan(state: DecisionState) -> Dict[str, Any]:
    logger.info(f"Node [receive_approved_plan] for automation {state.get('automation_id')}")
    auto_id = state.get("automation_id") or str(uuid.uuid4())
    return {
        "automation_id": auto_id,
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


# Node 3: ask_user (interrupt point)
def ask_user(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [ask_user]")
    plan = state.get("plan", {})
    ambiguities = plan.get("ambiguities", [])
    first_ambiguity = ambiguities[0] if ambiguities else {"question": "Could you clarify the automation details?"}
    question = first_ambiguity.get("question", "Please clarify")
    
    auto_id = state["automation_id"]
    # Save as draft in postgres
    persist_automation_record(
        plan=plan,
        status="draft",
        trigger_type=plan.get("trigger", {}).get("type", "threshold") if plan.get("trigger") else "threshold",
        automation_id=auto_id,
        user_id=state.get("user_id")
    )
    log_audit_event("ambiguity_asked", {"question": question, "field_path": first_ambiguity.get("field_path")}, auto_id)
    
    # LangGraph interrupt: pauses graph and awaits user response
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
    
    # Apply answer to plan trigger params
    if plan.get("trigger") and "params" in plan["trigger"]:
        trigger_params = dict(plan["trigger"]["params"])
        # If response contains a number, parse as threshold
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
    
    # Ensure default timezone for time-based triggers
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


# Node 6: persist_automation
def persist_automation(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [persist_automation]")
    plan = state.get("plan", {})
    final_trig = state.get("final_trigger", {})
    auto_id = state["automation_id"]
    
    # Persist as active in postgres
    persist_automation_record(
        plan=plan,
        status="active",
        trigger_type=final_trig.get("type", "threshold"),
        automation_id=auto_id,
        user_id=state.get("user_id")
    )
    log_audit_event("guardrail_approved", {"status": "active", "trigger": final_trig}, auto_id)
    
    return {
        "status": "active"
    }


# Node 7: handoff_to_trigger_engine
async def handoff_to_trigger_engine(state: DecisionState) -> Dict[str, Any]:
    logger.info("Node [handoff_to_trigger_engine]")
    auto_id = state["automation_id"]
    final_trig = state.get("final_trigger", {})
    plan = state.get("plan", {})
    
    # Hand off to trigger-engine service via internal REST call
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
        logger.warning(f"Could not reach trigger engine directly during handoff (expected if stub): {e}")

    return {
        "status": "active"
    }


# Build State Graph
def create_decision_graph(checkpointer: Optional[Any] = None):
    workflow = StateGraph(DecisionState)
    
    workflow.add_node("receive_approved_plan", receive_approved_plan)
    workflow.add_node("check_ambiguities", check_ambiguities)
    workflow.add_node("ask_user", ask_user)
    workflow.add_node("await_user_response", await_user_response)
    workflow.add_node("finalize_trigger_config", finalize_trigger_config)
    workflow.add_node("persist_automation", persist_automation)
    workflow.add_node("handoff_to_trigger_engine", handoff_to_trigger_engine)
    
    # Edge wiring
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
    workflow.add_edge("finalize_trigger_config", "persist_automation")
    workflow.add_edge("persist_automation", "handoff_to_trigger_engine")
    workflow.add_edge("handoff_to_trigger_engine", END)
    
    memory = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=memory)


decision_graph = create_decision_graph()
