import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, Optional
import redis

from .registry import invoke
from .db import check_and_record_idempotency, update_execution_status, log_audit_event

logger = logging.getLogger("execution-worker")

QUEUE_NAME = "automation_queue"
DEAD_LETTER_QUEUE = "dead_letter"


def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url, decode_responses=True)


async def process_job(job: Dict[str, Any]) -> bool:
    automation_id = job.get("automation_id", "")
    trigger_window_str = job.get("trigger_window_start")
    action_name = job.get("action_name", "")
    params = job.get("params", {})
    retries = job.get("retries", 0)

    try:
        trigger_window_start = datetime.fromisoformat(trigger_window_str)
    except Exception:
        trigger_window_start = datetime.now(timezone.utc)

    # 1. Idempotency check
    is_dup, prior_status = check_and_record_idempotency(automation_id, trigger_window_start, "running")
    if is_dup:
        logger.info(f"[Worker] Idempotent duplicate skipped: automation {automation_id} at {trigger_window_str}")
        return True

    # 2. Invoke action
    try:
        result = await invoke(action_name, params)
        if not result.success:
            raise RuntimeError(result.message or f"Action {action_name} returned failure status")
        update_execution_status(automation_id, trigger_window_start, "completed")
        log_audit_event("action_executed", {"action": action_name, "result": result.model_dump()}, automation_id)
        logger.info(f"[Worker] Successfully executed {action_name} for automation {automation_id}")
        return True
    except Exception as e:
        logger.error(f"[Worker] Failed executing {action_name} for automation {automation_id}: {e}")
        retries += 1
        job["retries"] = retries
        job["last_error"] = str(e)

        if retries >= 3:
            # Push to dead-letter queue
            r = get_redis_client()
            r.rpush(DEAD_LETTER_QUEUE, json.dumps(job))
            update_execution_status(automation_id, trigger_window_start, "dead_lettered")
            log_audit_event(
                "action_failed",
                {"action": action_name, "error": str(e), "dead_lettered": True, "attempts": retries},
                automation_id
            )
            logger.warning(f"[Worker] Job for automation {automation_id} exceeded max retries. Moved to {DEAD_LETTER_QUEUE}.")
            return False
        else:
            # Requeue with backoff
            r = get_redis_client()
            r.rpush(QUEUE_NAME, json.dumps(job))
            logger.info(f"[Worker] Job for automation {automation_id} re-queued (retry {retries}/3).")
            return False


async def worker_loop():
    logger.info("Execution worker loop started, listening to automation_queue")
    r = get_redis_client()
    while True:
        try:
            # Non-blocking pop with sleep to allow clean cancellation
            item = r.lpop(QUEUE_NAME)
            if item:
                job = json.loads(item)
                await process_job(job)
            else:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in execution worker loop: {e}")
            await asyncio.sleep(1.0)
