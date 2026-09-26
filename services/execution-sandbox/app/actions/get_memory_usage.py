import logging
import os
from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError

logger = logging.getLogger("execution-sandbox")


class EmptyParams(BaseModel):
    pass


async def get_memory_usage(params: EmptyParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent

    agent = get_online_host_agent()
    if agent:
        job_id = create_host_agent_job(
            host_agent_id=agent["id"],
            action_name="get_memory_usage",
            params=params.model_dump()
        )
        return ActionResult(
            success=True,
            message=f"Dispatched get_memory_usage job {job_id} to host agent {agent['id']}",
            details={"job_id": job_id, "host_agent_id": agent["id"], "status": "pending"}
        )

    # Container fallback if no host agent currently online
    try:
        if os.path.exists("/proc/meminfo"):
            meminfo = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        meminfo[key] = int(val)
            total_kb = meminfo.get("MemTotal", 0)
            avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used_kb = total_kb - avail_kb
            pct = round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0.0
            total_gb = round(total_kb / (1024 * 1024), 2)
            avail_gb = round(avail_kb / (1024 * 1024), 2)
            used_gb = round(used_kb / (1024 * 1024), 2)

            return ActionResult(
                success=True,
                message=f"Memory Usage: {pct}% ({used_gb} GB used of {total_gb} GB, {avail_gb} GB available)",
                details={
                    "percent": pct,
                    "total_gb": total_gb,
                    "available_gb": avail_gb,
                    "used_gb": used_gb,
                    "source": "container_fallback"
                }
            )
    except Exception as e:
        logger.warning(f"Failed to read /proc/meminfo fallback: {e}")

    raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")
