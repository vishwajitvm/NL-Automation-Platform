from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import pytz

from .queue import enqueue_job
from .db import update_last_fired

logger = logging.getLogger("trigger-engine")

scheduler = AsyncIOScheduler(timezone=pytz.utc)


def fire_time_job(automation_id: str, action_name: str, params: Dict[str, Any], trigger_info: Dict[str, Any]):
    now = datetime.now(timezone.utc)
    logger.info(f"Time trigger fired for automation {automation_id} at {now.isoformat()}")
    enqueue_job(automation_id, now, action_name, params, trigger_info=trigger_info)
    update_last_fired(automation_id, now)


def fire_delay_job(automation_id: str, action_name: str, params: Dict[str, Any], trigger_info: Dict[str, Any]):
    now = datetime.now(timezone.utc)
    logger.info(f"One-shot delay trigger fired for automation {automation_id} at {now.isoformat()}")
    enqueue_job(automation_id, now, action_name, params, trigger_info=trigger_info)
    update_last_fired(automation_id, now)


def schedule_delay_automation(automation_id: str, trigger_params: Dict[str, Any], action: Dict[str, Any]) -> str:
    delay_seconds = int(trigger_params.get("delay_seconds", 0))
    run_date = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

    action_name = action.get("name", "write_log_notification")
    action_params = action.get("params", {})
    trigger_info = {"type": "delay", "params": trigger_params}

    job_id = f"delay_job_{automation_id}"

    # Remove existing job if present
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    date_trigger = DateTrigger(run_date=run_date, timezone=pytz.utc)
    scheduler.add_job(
        fire_delay_job,
        trigger=date_trigger,
        id=job_id,
        args=[automation_id, action_name, action_params, trigger_info],
        replace_existing=True
    )
    logger.info(f"Scheduled one-shot delay job {job_id} to fire in {delay_seconds}s at {run_date.isoformat()}")
    return job_id


def schedule_time_automation(automation_id: str, trigger_params: Dict[str, Any], action: Dict[str, Any]) -> str:
    user_tz_str = trigger_params.get("timezone", "UTC")
    try:
        user_tz = pytz.timezone(user_tz_str)
    except Exception:
        user_tz = pytz.utc

    cron_expr = trigger_params.get("cron", "0 17 * * 5")
    parts = cron_expr.split()
    
    action_name = action.get("name", "send_email")
    action_params = action.get("params", {})
    trigger_info = {"type": "time", "params": trigger_params}

    job_id = f"time_job_{automation_id}"

    # Remove existing job if present
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        cron_trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=user_tz
        )
        scheduler.add_job(
            fire_time_job,
            trigger=cron_trigger,
            id=job_id,
            args=[automation_id, action_name, action_params, trigger_info],
            replace_existing=True
        )
        logger.info(f"Scheduled time job {job_id} with cron '{cron_expr}' in timezone {user_tz_str}")
        return job_id
    else:
        logger.error(f"Invalid cron expression: {cron_expr}")
        return ""
