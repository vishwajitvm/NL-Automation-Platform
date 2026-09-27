from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    time = "time"
    threshold = "threshold"
    event = "event"
    immediate = "immediate"
    delay = "delay"


class Trigger(BaseModel):
    type: TriggerType
    params: dict[str, Any]  # e.g. {"cron": "0 17 * * 5"} or {"metric": "disk_usage_pct", "threshold": 80, "comparator": ">="}


class Action(BaseModel):
    name: str  # must match a registered action in execution-sandbox
    params: dict[str, Any]
    risk_tier: Literal["low", "medium", "high"] = "low"


class Ambiguity(BaseModel):
    field_path: str   # e.g. "trigger.params.threshold"
    question: str


class AutomationPlan(BaseModel):
    raw_text: str
    trigger: Trigger | None = None
    action: Action | None = None
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    parseable: bool = True
    degraded_mode: bool = False
