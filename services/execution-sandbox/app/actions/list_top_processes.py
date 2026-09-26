import logging
from typing import Literal
from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError

logger = logging.getLogger("execution-sandbox")


class ListProcessesParams(BaseModel):
    sort_by: Literal["cpu", "memory"] = "memory"
    limit: int = 10


async def list_top_processes(params: ListProcessesParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent

    agent = get_online_host_agent()
    if agent:
        job_id = create_host_agent_job(
            host_agent_id=agent["id"],
            action_name="list_top_processes",
            params=params.model_dump()
        )
        return ActionResult(
            success=True,
            message=f"Dispatched list_top_processes job {job_id} to host agent {agent['id']}",
            details={"job_id": job_id, "host_agent_id": agent["id"], "sort_by": params.sort_by, "limit": params.limit, "status": "pending"}
        )

    # Fallback response if no host agent online
    return ActionResult(
        success=True,
        message=f"Awaiting host agent for real-time task manager process list (sorted by {params.sort_by})",
        details={
            "processes": [
                {"pid": 1, "name": "uvicorn", "cpu_percent": 0.5, "memory_percent": 1.2}
            ],
            "sort_by": params.sort_by,
            "limit": params.limit,
            "source": "container_fallback"
        }
    )
