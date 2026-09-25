from typing import Optional
from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError


class EmptyTrashParams(BaseModel):
    drive: Optional[str] = None
    force: bool = False


async def empty_trash(params: EmptyTrashParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent
    agent = get_online_host_agent()
    if not agent:
        raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")

    job_id = create_host_agent_job(
        host_agent_id=agent["id"],
        action_name="empty_trash",
        params=params.model_dump()
    )
    return ActionResult(
        success=True,
        message=f"Dispatched empty_trash job {job_id} to host agent {agent['id']}",
        details={"job_id": job_id, "host_agent_id": agent["id"], "status": "pending"}
    )
