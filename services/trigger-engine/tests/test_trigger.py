import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.metrics import set_metric, get_metric
from app.threshold_watcher import check_and_fire_threshold_automations
from app.time_triggers import schedule_time_automation, scheduler
from app.queue import QUEUE_NAME


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_threshold_fires_and_cooldown_suppresses(monkeypatch):
    """
    Threshold-based automation fires when condition is met.
    A second poll inside the cooldown window is correctly suppressed.
    """
    auto_id = str(uuid.uuid4())
    enqueued_jobs = []

    def mock_enqueue(aid, window, action, params, trigger_info=None):
        enqueued_jobs.append({"automation_id": aid, "action": action, "params": params})

    mock_db = [
        {
            "id": auto_id,
            "structured_plan": {
                "trigger": {
                    "type": "threshold",
                    "params": {"metric": "test_recycle_pct", "threshold": 80, "comparator": ">="}
                },
                "action": {"name": "empty_recycle_bin", "params": {}}
            },
            "status": "active",
            "trigger_type": "threshold",
            "cooldown_seconds": 300,
            "last_fired_at": None
        }
    ]

    def mock_get_automations(trigger_type=None):
        return mock_db

    def mock_update_last_fired(aid, fired_at):
        for a in mock_db:
            if a["id"] == aid:
                a["last_fired_at"] = fired_at

    monkeypatch.setattr("app.threshold_watcher.get_active_automations", mock_get_automations)
    monkeypatch.setattr("app.threshold_watcher.enqueue_job", mock_enqueue)
    monkeypatch.setattr("app.threshold_watcher.update_last_fired", mock_update_last_fired)

    # 1. Condition not met (70% < 80%)
    set_metric("test_recycle_pct", 70.0)
    fired1 = check_and_fire_threshold_automations()
    assert len(fired1) == 0
    assert len(enqueued_jobs) == 0

    # 2. Condition met (85% >= 80%)
    set_metric("test_recycle_pct", 85.0)
    now1 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    fired2 = check_and_fire_threshold_automations(custom_now=now1)
    assert auto_id in fired2
    assert len(enqueued_jobs) == 1
    assert enqueued_jobs[0]["action"] == "empty_recycle_bin"

    # 3. Flapping check: Condition still met 30 seconds later (within 300s cooldown)
    now2 = now1 + timedelta(seconds=30)
    fired3 = check_and_fire_threshold_automations(custom_now=now2)
    # Must be suppressed by cooldown!
    assert len(fired3) == 0
    assert len(enqueued_jobs) == 1  # Still 1, not duplicate!

    # 4. After cooldown expires (305 seconds later): fires again!
    now3 = now1 + timedelta(seconds=305)
    fired4 = check_and_fire_threshold_automations(custom_now=now3)
    assert auto_id in fired4
    assert len(enqueued_jobs) == 2


@pytest.mark.asyncio
async def test_time_based_schedule_utc():
    """
    Time-based automation schedules with explicit user timezone converted to UTC.
    """
    auto_id = str(uuid.uuid4())
    params = {"cron": "0 17 * * 5", "timezone": "America/New_York"}
    action = {"name": "send_email", "params": {"to": "user@example.com"}}

    job_id = schedule_time_automation(auto_id, params, action)
    assert job_id == f"time_job_{auto_id}"

    job = scheduler.get_job(job_id)
    assert job is not None


@pytest.mark.asyncio
async def test_metrics_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/metrics/test_disk", json={"value": 92.5})
        assert resp.status_code == 200

        resp2 = await ac.get("/metrics/test_disk")
        assert resp2.status_code == 200
        assert resp2.json()["value"] == 92.5
