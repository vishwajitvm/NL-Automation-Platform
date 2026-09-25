from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ActionResult:
    def __init__(self, success: bool, message: str, details: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "details": self.details,
        }


class TrashBackend(ABC):
    @abstractmethod
    def get_usage_pct(self) -> float:
        """
        % of the trash folder's volume capacity currently used by trash contents:
        trash folder byte size / total capacity of the disk/volume hosting user's home directory * 100.
        """
        pass

    @abstractmethod
    def empty(self) -> ActionResult:
        """
        Clears trash contents and returns ActionResult.
        """
        pass
