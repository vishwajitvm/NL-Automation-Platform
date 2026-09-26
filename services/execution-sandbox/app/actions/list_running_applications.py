from pydantic import BaseModel
from ..registry import ActionResult

class EmptyParams(BaseModel):
    pass

async def list_running_applications(params: EmptyParams) -> ActionResult:
    # This is a host-bound action, dispatched via host_agent_jobs table
    return ActionResult(success=True, output="Dispatched to host agent")
