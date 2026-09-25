import pytest
import uuid
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.registry import invoke
from app.actions.common import ActionNotRegisteredError, ActionNotAvailableError
import app.main as main_module


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_unregistered_action_hard_error():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/execute", json={
            "action_name": "format_disk",
            "params": {}
        })
        assert resp.status_code == 400
        assert "ActionNotRegisteredError" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_direct_invoke_unregistered_raises():
    with pytest.raises(ActionNotRegisteredError):
        await invoke("delete_database", {})


@pytest.mark.asyncio
async def test_invalid_parameters_pydantic_validation_error():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid URL for send_webhook
        resp = await ac.post("/execute", json={
            "action_name": "send_webhook",
            "params": {"url": "not-a-valid-url"}
        })
        assert resp.status_code == 400
        assert "InvalidParametersError" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_empty_recycle_bin_host_boundary_error():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/execute", json={
            "action_name": "empty_recycle_bin",
            "params": {}
        })
        assert resp.status_code == 400
        assert "ActionNotAvailableError" in resp.json()["detail"]
        assert "host-boundary" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_idempotency_duplicate_trigger_fire(monkeypatch):
    """
    Same (automation_id, trigger_window_start) invoked twice
    -> second call short-circuits via execution_log with single side effect.
    """
    seen_windows = set()

    def mock_check_idempotency(auto_id, window, status="running"):
        key = (auto_id, window.isoformat())
        if key in seen_windows:
            return (True, "completed")
        seen_windows.add(key)
        return (False, None)

    monkeypatch.setattr(main_module, "check_and_record_idempotency", mock_check_idempotency)
    monkeypatch.setattr(main_module, "update_execution_status", lambda *args: None)
    monkeypatch.setattr(main_module, "log_audit_event", lambda *args: None)

    transport = ASGITransport(app=app)
    auto_id = str(uuid.uuid4())
    window = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc).isoformat()

    payload = {
        "action_name": "write_log_notification",
        "params": {"message": "Test notification", "level": "info"},
        "automation_id": auto_id,
        "trigger_window_start": window
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First call: executes normally
        resp1 = await ac.post("/execute", json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["success"] is True
        assert resp1.json().get("status") != "skipped"

        # Second call with same automation_id and trigger_window_start: short-circuits
        resp2 = await ac.post("/execute", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "skipped"
        assert "idempotent_duplicate" in resp2.json()["reason"]


@pytest.mark.asyncio
async def test_mcp_tools_exposure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/mcp/tools")
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        tool_names = [t["name"] for t in tools]
        assert "send_email" in tool_names
        assert "send_webhook" in tool_names
        assert "write_log_notification" in tool_names
        assert "run_http_healthcheck" in tool_names
        assert "empty_recycle_bin" in tool_names


@pytest.mark.asyncio
async def test_dead_letter_queue_after_3_retries(monkeypatch):
    """
    Forcing an action to fail -> after 3 attempts, lands in dead_letter,
    and writes audit log entry with dead_lettered=true.
    """
    import json
    from app.worker import process_job, DEAD_LETTER_QUEUE

    dead_letter_items = []
    audit_events = []

    class MockRedis:
        def rpush(self, queue_name, payload):
            if queue_name == DEAD_LETTER_QUEUE:
                dead_letter_items.append(json.loads(payload))

    monkeypatch.setattr("app.worker.get_redis_client", lambda: MockRedis())
    monkeypatch.setattr("app.worker.check_and_record_idempotency", lambda *args: (False, None))
    monkeypatch.setattr("app.worker.update_execution_status", lambda *args: None)

    def mock_log_audit(event_type, payload, auto_id=None):
        audit_events.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.worker.log_audit_event", mock_log_audit)

    # Action that fails
    job = {
        "automation_id": str(uuid.uuid4()),
        "trigger_window_start": datetime.now(timezone.utc).isoformat(),
        "action_name": "run_http_healthcheck",
        "params": {"url": "http://invalid-destination-does-not-exist.test:9999"},
        "retries": 2  # Already failed twice, this is attempt #3
    }

    # Attempt 3: fails and should land in dead_letter
    success = await process_job(job)
    assert success is False
    assert len(dead_letter_items) == 1
    assert dead_letter_items[0]["retries"] == 3
    assert any(
        e["event_type"] == "action_failed" and e["payload"].get("dead_lettered") is True
        for e in audit_events
    )

