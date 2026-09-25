from typing import Any, Optional
from pydantic import BaseModel


class ActionResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None


class ActionNotRegisteredError(Exception):
    def __init__(self, action_name: str):
        super().__init__(f"Action '{action_name}' is not registered.")
        self.action_name = action_name


class ActionNotAvailableError(Exception):
    def __init__(self, message: str = "host-boundary action, requires v2 host agent — not available in Docker-only MVP"):
        super().__init__(message)
