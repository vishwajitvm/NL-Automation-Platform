import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

from shared.logging_config import setup_logging_and_middleware
from .actions.common import ActionNotRegisteredError, ActionNotAvailableError, ActionResult
from .registry import invoke, get_mcp_tools, REGISTRY
from .db import check_and_record_idempotency, update_execution_status, log_audit_event
from .worker import worker_loop

logger = logging.getLogger("execution-sandbox")
worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global worker_task
    worker_task = asyncio.create_task(worker_loop())
    logger.info("Execution sandbox background worker started")
    yield
    # Shutdown
    if worker_task:
        worker_task.cancel()
    logger.info("Execution sandbox background worker stopped")


app = FastAPI(title="Execution Sandbox (MCP Action Registry)", version="1.0.0", lifespan=lifespan)
setup_logging_and_middleware(app, "execution-sandbox")


class ExecuteRequest(BaseModel):
    action_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    automation_id: Optional[str] = None
    trigger_window_start: Optional[datetime] = None


class MCPCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "execution-sandbox"}


@app.get("/mcp/tools")
def list_mcp_tools():
    """Returns declared MCP tools from the fixed action registry"""
    return {"tools": get_mcp_tools()}


@app.post("/mcp/call")
async def call_mcp_tool(req: MCPCallRequest):
    """Executes a declared MCP tool strictly through the action registry"""
    return await execute_action(
        ExecuteRequest(action_name=req.name, params=req.arguments)
    )


@app.post("/execute")
async def execute_action(req: ExecuteRequest):
    action_name = req.action_name
    params = req.params

    # 1. Idempotency check if automation_id and trigger_window_start provided
    if req.automation_id and req.trigger_window_start:
        is_dup, prior_status = check_and_record_idempotency(
            req.automation_id, req.trigger_window_start
        )
        if is_dup:
            logger.info(f"Duplicate trigger fire suppressed for automation {req.automation_id} at {req.trigger_window_start}")
            return {
                "success": True,
                "status": "skipped",
                "reason": f"idempotent_duplicate (prior status: {prior_status})"
            }

    # 2. Invoke registry
    try:
        result: ActionResult = await invoke(action_name, params)
        
        # Log success to audit_log
        if req.automation_id:
            if req.trigger_window_start:
                update_execution_status(req.automation_id, req.trigger_window_start, "completed")
            log_audit_event("action_executed", {"action": action_name, "result": result.model_dump()}, req.automation_id)

        return {"success": result.success, "data": result.data, "message": result.message}

    except ActionNotRegisteredError as e:
        logger.error(f"Unregistered action attempt: {action_name}")
        if req.automation_id:
            if req.trigger_window_start:
                update_execution_status(req.automation_id, req.trigger_window_start, "failed")
            log_audit_event("action_failed", {"action": action_name, "error": str(e)}, req.automation_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ActionNotRegisteredError: Action '{action_name}' is not in the registry."
        )

    except ValidationError as e:
        logger.error(f"Validation error for action {action_name}: {e}")
        if req.automation_id:
            if req.trigger_window_start:
                update_execution_status(req.automation_id, req.trigger_window_start, "failed")
            log_audit_event("action_failed", {"action": action_name, "error": str(e)}, req.automation_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"InvalidParametersError: {e.errors()}"
        )

    except ActionNotAvailableError as e:
        logger.warning(f"Action unavailable (host-boundary): {action_name}")
        if req.automation_id:
            if req.trigger_window_start:
                update_execution_status(req.automation_id, req.trigger_window_start, "unavailable")
            log_audit_event("action_failed", {"action": action_name, "error": str(e)}, req.automation_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ActionNotAvailableError: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error executing {action_name}: {e}")
        if req.automation_id:
            if req.trigger_window_start:
                update_execution_status(req.automation_id, req.trigger_window_start, "failed")
            log_audit_event("action_failed", {"action": action_name, "error": str(e)}, req.automation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ExecutionError: {str(e)}"
        )
