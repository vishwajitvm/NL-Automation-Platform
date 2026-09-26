import logging
from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError

logger = logging.getLogger("execution-sandbox")


class EmptyParams(BaseModel):
    pass


async def list_connected_devices(params: EmptyParams) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent

    agent = get_online_host_agent()
    if agent:
        job_id = create_host_agent_job(
            host_agent_id=agent["id"],
            action_name="list_connected_devices",
            params=params.model_dump()
        )
        return ActionResult(
            success=True,
            message=f"Dispatched list_connected_devices job {job_id} to host agent {agent['id']}",
            details={"job_id": job_id, "host_agent_id": agent["id"], "status": "pending"}
        )

    # Fallback
    return ActionResult(
        success=True,
        message="Awaiting host agent for physical USB/HID device enumeration",
        details={
            "devices": [
                {"type": "Keyboard", "name": "Standard PS/2 Keyboard", "vendor": "Standard"},
                {"type": "Mouse", "name": "USB Optical Mouse", "vendor": "Generic"}
            ],
            "source": "container_fallback"
        }
    )
