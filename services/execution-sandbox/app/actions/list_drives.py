from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError


class ListDrivesParams(BaseModel):
    pass


async def list_drives(params: ListDrivesParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent
    agent = get_online_host_agent()
    if not agent:
        raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")

    job_id = create_host_agent_job(
        host_agent_id=agent["id"],
        action_name="list_drives",
        params=params.model_dump()
    )
    return ActionResult(
        success=True,
        message=f"Dispatched list_drives job {job_id} to host agent {agent['id']}",
        details={"job_id": job_id, "host_agent_id": agent["id"], "status": "pending"}
    )
