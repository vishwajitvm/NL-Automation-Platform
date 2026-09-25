from pydantic import BaseModel, Field
from .common import ActionResult, ActionNotAvailableError
from ..safety.denylist import validate_path_safety


class DeletePathParams(BaseModel):
    path: str = Field(..., description="Target file or directory path to delete")
    dry_run: bool = Field(False, description="If true, generates preview count and total size without deleting")


async def delete_path(params: DeletePathParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent

    # 1. Hard denylist check before anything else
    safe, refusal = validate_path_safety(params.path)
    if not safe:
        return ActionResult(
            success=False,
            message=refusal,
            details={"path": params.path, "denylisted": True}
        )

    agent = get_online_host_agent()
    if not agent:
        raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")

    action_to_dispatch = "preview_delete_path" if params.dry_run else "delete_path"

    job_id = create_host_agent_job(
        host_agent_id=agent["id"],
        action_name=action_to_dispatch,
        params=params.model_dump()
    )
    return ActionResult(
        success=True,
        message=f"Dispatched {action_to_dispatch} job {job_id} for '{params.path}' to host agent {agent['id']}",
        details={"job_id": job_id, "host_agent_id": agent["id"], "path": params.path, "status": "pending", "dry_run": params.dry_run}
    )
