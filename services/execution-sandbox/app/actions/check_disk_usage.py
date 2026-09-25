from pydantic import BaseModel, Field
from .common import ActionResult, ActionNotAvailableError


class CheckDiskUsageParams(BaseModel):
    drive: str = Field(..., description="Drive letter or mount point to check, e.g. 'C:\\' or '/'")


async def check_disk_usage(params: CheckDiskUsageParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent
    agent = get_online_host_agent()
    if not agent:
        raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")

    job_id = create_host_agent_job(
        host_agent_id=agent["id"],
        action_name="check_disk_usage",
        params=params.model_dump()
    )
    return ActionResult(
        success=True,
        message=f"Dispatched check_disk_usage job {job_id} for drive '{params.drive}' to host agent {agent['id']}",
        details={"job_id": job_id, "host_agent_id": agent["id"], "drive": params.drive, "status": "pending"}
    )
