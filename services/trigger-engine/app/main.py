import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.logging_config import setup_logging_and_middleware
from .time_triggers import scheduler, schedule_time_automation, schedule_delay_automation
from .threshold_watcher import check_and_fire_threshold_automations
from .metrics import get_metric, set_metric, MOCK_METRICS

logger = logging.getLogger("trigger-engine")

watcher_task = None


async def threshold_polling_loop():
    poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    logger.info(f"Starting threshold watcher loop with interval {poll_interval}s")
    while True:
        try:
            check_and_fire_threshold_automations()
        except Exception as e:
            logger.error(f"Error in threshold polling loop: {e}")
        await asyncio.sleep(poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.start()
    global watcher_task
    watcher_task = asyncio.create_task(threshold_polling_loop())
    logger.info("Trigger engine started (APScheduler + Threshold Watcher)")
    yield
    # Shutdown
    if watcher_task:
        watcher_task.cancel()
    scheduler.shutdown()
    logger.info("Trigger engine stopped")


app = FastAPI(title="Trigger Engine Service", version="1.0.0", lifespan=lifespan)
setup_logging_and_middleware(app, "trigger-engine")


class TriggerRegistrationRequest(BaseModel):
    automation_id: str
    trigger: Dict[str, Any]
    action: Dict[str, Any]


class MetricUpdateRequest(BaseModel):
    value: float


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "trigger-engine"}


@app.get("/metrics/{metric_name}")
def read_metric(metric_name: str):
    val = get_metric(metric_name)
    return {"metric": metric_name, "value": val}


@app.post("/metrics/{metric_name}")
def update_metric(metric_name: str, req: MetricUpdateRequest):
    set_metric(metric_name, req.value)
    return {"metric": metric_name, "value": req.value, "updated": True}


@app.post("/poll")
def trigger_manual_poll():
    """Triggers an immediate threshold evaluation round"""
    fired = check_and_fire_threshold_automations()
    return {"fired_count": len(fired), "fired_ids": fired}


@app.post("/triggers")
def register_trigger(req: TriggerRegistrationRequest):
    auto_id = req.automation_id
    trig = req.trigger
    trig_type = trig.get("type", "threshold")
    params = trig.get("params", {})
    action = req.action

    if trig_type == "time":
        job_id = schedule_time_automation(auto_id, params, action)
        return {"status": "registered", "type": "time", "job_id": job_id}
    elif trig_type == "delay":
        job_id = schedule_delay_automation(auto_id, params, action)
        return {"status": "registered", "type": "delay", "job_id": job_id}
    elif trig_type == "threshold":
        # Threshold triggers are evaluated in polling loop from active automations in DB
        return {"status": "registered", "type": "threshold"}
    else:
        return {"status": "registered", "type": trig_type}


@app.delete("/triggers/{automation_id}")
def unregister_trigger(automation_id: str):
    time_job_id = f"time_job_{automation_id}"
    delay_job_id = f"delay_job_{automation_id}"
    removed = []
    if scheduler.get_job(time_job_id):
        scheduler.remove_job(time_job_id)
        removed.append(time_job_id)
    if scheduler.get_job(delay_job_id):
        scheduler.remove_job(delay_job_id)
        removed.append(delay_job_id)

    if removed:
        return {"status": "unregistered", "job_ids": removed}
    return {"status": "unregistered", "message": "No active scheduled job found"}
