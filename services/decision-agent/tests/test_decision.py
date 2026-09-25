import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db import sweep_expired_drafts, persist_automation_record
from shared.schemas.plan import AutomationPlan, Trigger, Action, Ambiguity
import app.main as main_module


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_unambiguous_plan_resolves_directly_to_active(monkeypatch):
    """
    Low-risk unambiguous plan should bypass interrupts and resolve directly to active.
    """
    monkeypatch.setattr("app.db.persist_automation_record", lambda **kwargs: str(uuid.uuid4()))
    monkeypatch.setattr("app.db.log_audit_event", lambda *args: None)

    plan = AutomationPlan(
        raw_text="email me a summary every Friday at 5pm",
        trigger=Trigger(type="time", params={"cron": "0 17 * * 5", "timezone": "UTC"}),
        action=Action(name="send_email", params={"to": "test@example.com", "subject": "Summary"}),
        ambiguities=[],
        parseable=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/resolve", json={"plan": plan.model_dump()})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["final_trigger"]["type"] == "time"


@pytest.mark.asyncio
async def test_ambiguous_plan_pauses_and_resumes_correctly(monkeypatch):
    """
    Plan with ambiguity pauses at ask_user, returns clarifying question,
    and resumes correctly when answered via /resume.
    """
    monkeypatch.setattr("app.db.persist_automation_record", lambda **kwargs: kwargs.get("automation_id", str(uuid.uuid4())))
    monkeypatch.setattr("app.db.log_audit_event", lambda *args: None)

    auto_id = str(uuid.uuid4())
    plan = AutomationPlan(
        raw_text="notify me when disk is full",
        trigger=Trigger(type="threshold", params={"metric": "disk_usage_pct"}),
        action=Action(name="write_log_notification", params={"level": "warning"}),
        ambiguities=[
            Ambiguity(
                field_path="trigger.params.threshold",
                question="At what disk percentage should notification trigger?"
            )
        ],
        parseable=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Submit ambiguous plan -> should pause at interrupt
        resp1 = await ac.post("/resolve", json={
            "plan": plan.model_dump(),
            "automation_id": auto_id
        })
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "draft"
        assert "disk percentage" in data1["clarification_question"]

        # Step 2: Answer the clarifying question -> resumes graph
        resp2 = await ac.post("/resume", json={
            "automation_id": auto_id,
            "user_response": "when disk reaches 90%"
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "active"
        assert data2["final_trigger"]["params"]["threshold"] == 90


@pytest.mark.asyncio
async def test_destructive_action_confirmation_flow(monkeypatch):
    """
    High-risk action (delete_path) pauses at await_confirmation with preview data,
    then executes and records confirmation upon multi-step approval.
    """
    monkeypatch.setattr("app.db.persist_automation_record", lambda **kwargs: kwargs.get("automation_id", str(uuid.uuid4())))
    monkeypatch.setattr("app.db.log_audit_event", lambda *args: None)

    recorded_confirmations = []

    def mock_record_confirmation(step, automation_id=None, command_id=None, target_path=None, user_id=None, details=None):
        cid = str(uuid.uuid4())
        recorded_confirmations.append({"id": cid, "step": step, "target_path": target_path})
        return cid

    monkeypatch.setattr("app.graph.record_destructive_action_confirmation", mock_record_confirmation)

    auto_id = str(uuid.uuid4())
    plan = AutomationPlan(
        raw_text="delete folder C:\\temp\\old_build",
        trigger=Trigger(type="immediate", params={}),
        action=Action(name="delete_path", params={"path": "C:\\temp\\old_build"}),
        ambiguities=[],
        parseable=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Initial resolve -> pauses at await_confirmation
        resp1 = await ac.post("/resolve", json={
            "plan": plan.model_dump(),
            "automation_id": auto_id
        })
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "draft"
        assert data1["confirmation_required"] is True
        assert data1["risk_tier"] == "high"
        assert "preview" in data1

        # Step 2: Resume with 3-step SweetAlert2 confirmation payload
        resp2 = await ac.post("/resume", json={
            "automation_id": auto_id,
            "user_response": {
                "confirmed": True,
                "steps": ["preview", "typed_path", "final"],
                "path": "C:\\temp\\old_build"
            }
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "active"

        # Verify all 3 steps recorded individually
        steps_recorded = [r["step"] for r in recorded_confirmations]
        assert "preview" in steps_recorded
        assert "typed_path" in steps_recorded
        assert "final" in steps_recorded


def test_draft_expiry_sweeper_time_travel(monkeypatch):
    """
    Time-travel test: Unanswered draft older than 24h is auto-archived.
    """
    auto_id = str(uuid.uuid4())
    plan = {"raw_text": "unanswered draft"}

    mock_db = {
        auto_id: {
            "status": "draft",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=25)
        }
    }
    audit_events = []

    def mock_sweep(cutoff_delta=timedelta(hours=24), custom_now=None):
        now = custom_now or datetime.now(timezone.utc)
        cutoff = now - cutoff_delta
        archived = []
        for aid, rec in mock_db.items():
            if rec["status"] == "draft" and rec["created_at"] < cutoff:
                rec["status"] = "archived"
                archived.append(aid)
                audit_events.append({"event_type": "ambiguity_resolved", "reason": "expired_unanswered"})
        return archived

    monkeypatch.setattr("app.db.sweep_expired_drafts", mock_sweep)

    simulated_future = datetime.now(timezone.utc) + timedelta(hours=25)
    archived_ids = mock_sweep(custom_now=simulated_future)

    assert auto_id in archived_ids
    assert mock_db[auto_id]["status"] == "archived"
    assert any(e["reason"] == "expired_unanswered" for e in audit_events)
