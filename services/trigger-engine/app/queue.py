import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import redis

from .db import log_audit_event

logger = logging.getLogger("trigger-engine")

QUEUE_NAME = "automation_queue"


def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


def enqueue_job(
    automation_id: str,
    trigger_window_start: datetime,
    action_name: str,
    params: Dict[str, Any],
    trigger_info: Optional[Dict[str, Any]] = None
) -> None:
    job = {
        "automation_id": str(automation_id),
        "trigger_window_start": trigger_window_start.isoformat(),
        "action_name": action_name,
        "params": params,
        "retries": 0
    }
    try:
        r = get_redis_client()
        r.rpush(QUEUE_NAME, json.dumps(job))
        logger.info(f"Enqueued job for automation {automation_id} at {trigger_window_start.isoformat()}")
        log_audit_event(
            "trigger_fired",
            {"trigger": trigger_info or {}, "action": action_name, "window": trigger_window_start.isoformat()},
            automation_id
        )
    except Exception as e:
        logger.error(f"Failed to enqueue job to Redis: {e}")
