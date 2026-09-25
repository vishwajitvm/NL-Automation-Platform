from typing import Optional
from pydantic import BaseModel
from .common import ActionResult, ActionNotAvailableError


class EmptyRecycleBinParams(BaseModel):
    drive: Optional[str] = None


async def empty_recycle_bin(params: EmptyRecycleBinParams) -> ActionResult:
    raise ActionNotAvailableError("host-boundary action, requires v2 host agent — not available in Docker-only MVP")
