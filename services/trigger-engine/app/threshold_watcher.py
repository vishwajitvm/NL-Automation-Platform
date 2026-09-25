from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from .db import get_active_automations, update_last_fired, get_recent_host_agent_metric
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

        # Check if host agent pushed this metric recently, otherwise fall back to mock endpoint
        metric_source = "mock_fallback"
        host_metric = get_recent_host_agent_metric(metric_name, max_age_seconds=60)
        if host_metric is not None:
            current_val = host_metric
            metric_source = "host_agent"
        else:
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
        action_name = action.get("name", "empty_trash")
        action_params = action.get("params", {})
        trigger_info_copy = dict(trigger)
        trigger_info_copy["metric_source"] = metric_source
        trigger_info_copy["current_val"] = current_val

        enqueue_job(auto_id, now, action_name, action_params, trigger_info=trigger_info_copy)
        update_last_fired(auto_id, now)
        fired_ids.append(auto_id)
        logger.info(f"Fired threshold automation {auto_id} for metric {metric_name}={current_val} (source={metric_source})")

    return fired_ids
