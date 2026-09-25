import logging
from typing import Literal
from pydantic import BaseModel
from .common import ActionResult

logger = logging.getLogger("action-runner")


class WriteLogParams(BaseModel):
    message: str
    level: Literal["info", "warning", "error"] = "info"


async def write_log_notification(params: WriteLogParams) -> ActionResult:
    log_fn = getattr(logger, params.level, logger.info)
    log_fn(f"[NOTIFICATION] {params.message}")
    return ActionResult(
        success=True,
        data={"message": params.message, "level": params.level},
        message=f"Log notification written at level {params.level}"
    )
