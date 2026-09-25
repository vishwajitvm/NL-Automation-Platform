from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from .db import get_active_automations, update_last_fired
from .metrics import get_metric
from .queue import enqueue_job

logger = logging.getLogger("trigger-engine")


def evaluate_threshold_condition(current_val: float, comparator: str, threshold: float) -> bool:
    if comparator in (">=", "=>"):
        return current_val >= threshold
    elif comparator in (">",):
        return current_val > threshold
    elif comparator in ("<=", "=<"):
        return current_val <= threshold
    elif comparator in ("<",):
        return current_val < threshold
    elif comparator in ("==", "="):
        return current_val == threshold
    return current_val >= threshold


def check_and_fire_threshold_automations(custom_now: Optional[datetime] = None) -> List[str]:
    """
    Evaluates all active threshold-based automations against metrics.
    Applies cooldown window debouncing: if (now - last_fired_at) < cooldown_seconds, skips.
    Returns list of fired automation IDs.
    """
    now = custom_now or datetime.now(timezone.utc)
    active_automations = get_active_automations(trigger_type="threshold")
    fired_ids = []

    for auto in active_automations:
        auto_id = str(auto["id"])
        structured_plan = auto.get("structured_plan", {})
        trigger = structured_plan.get("trigger", {})
        params = trigger.get("params", {})
        action = structured_plan.get("action", {})

        metric_name = params.get("metric", "recycle_bin_percentage")
        threshold_val = float(params.get("threshold", 80))
        comparator = params.get("comparator", ">=")

        current_val = get_metric(metric_name)
        condition_met = evaluate_threshold_condition(current_val, comparator, threshold_val)

        if not condition_met:
            continue

        # Cooldown check to prevent flapping
        last_fired_at = auto.get("last_fired_at")
        cooldown_seconds = auto.get("cooldown_seconds", 300)

        if last_fired_at:
            if last_fired_at.tzinfo is None:
                last_fired_at = last_fired_at.replace(tzinfo=timezone.utc)
            elapsed = (now - last_fired_at).total_seconds()
            if elapsed < cooldown_seconds:
                logger.info(f"Automation {auto_id} met threshold condition but suppressed by cooldown ({elapsed:.1f}s < {cooldown_seconds}s)")
                continue

        # Condition met and outside cooldown window: fire!
        action_name = action.get("name", "empty_recycle_bin")
        action_params = action.get("params", {})
        enqueue_job(auto_id, now, action_name, action_params, trigger_info=trigger)
        update_last_fired(auto_id, now)
        fired_ids.append(auto_id)
        logger.info(f"Fired threshold automation {auto_id} for metric {metric_name}={current_val}")

    return fired_ids
