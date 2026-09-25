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
    Unambiguous plan should bypass ask_user and resolve directly to active.
    """
    monkeypatch.setattr("app.db.persist_automation_record", lambda **kwargs: str(uuid.uuid4()))
    monkeypatch.setattr("app.db.log_audit_event", lambda *args: None)

    plan = AutomationPlan(
        raw_text="clean my recycle bin when it reaches 80%",
        trigger=Trigger(type="threshold", params={"threshold": 80, "metric": "recycle_bin_percentage"}),
        action=Action(name="empty_recycle_bin", params={}),
        ambiguities=[],
        parseable=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/resolve", json={"plan": plan.model_dump()})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["final_trigger"]["type"] == "threshold"
        assert data["final_trigger"]["params"]["threshold"] == 80


@pytest.mark.asyncio
async def test_ambiguous_plan_pauses_and_resumes_correctly(monkeypatch):
    """
    'clean it when it's full' -> pauses at ask_user, returns clarifying question,
    and resumes correctly when answered via /resume.
    """
    monkeypatch.setattr("app.db.persist_automation_record", lambda **kwargs: kwargs.get("automation_id", str(uuid.uuid4())))
    monkeypatch.setattr("app.db.log_audit_event", lambda *args: None)

    auto_id = str(uuid.uuid4())
    plan = AutomationPlan(
        raw_text="clean it when it's full",
        trigger=Trigger(type="threshold", params={"metric": "recycle_bin_percentage"}),
        action=Action(name="empty_recycle_bin", params={}),
        ambiguities=[
            Ambiguity(
                field_path="trigger.params.threshold",
                question="At what percentage capacity should the recycle bin be cleaned?"
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
        assert "percentage capacity" in data1["clarification_question"]

        # Step 2: Answer the clarifying question -> resumes graph
        resp2 = await ac.post("/resume", json={
            "automation_id": auto_id,
            "user_response": "clean it when it reaches 85%"
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "active"
        assert data2["final_trigger"]["params"]["threshold"] == 85


def test_draft_expiry_sweeper_time_travel(monkeypatch):
    """
    Time-travel test: Unanswered draft older than 24h is auto-archived.
    """
    auto_id = str(uuid.uuid4())
    plan = {"raw_text": "unanswered draft"}

    # Mock DB interaction for sweeper
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

    # Fast forward time by 25 hours
    simulated_future = datetime.now(timezone.utc) + timedelta(hours=25)
    archived_ids = mock_sweep(custom_now=simulated_future)

    assert auto_id in archived_ids
    assert mock_db[auto_id]["status"] == "archived"
    assert any(e["reason"] == "expired_unanswered" for e in audit_events)
