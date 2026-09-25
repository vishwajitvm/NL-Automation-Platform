import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.providers import (
    ProviderChain,
    LLMProvider,
    RateLimitError,
    ParsedResult
)
from shared.schemas.plan import Trigger, Action, Ambiguity
import app.main as main_module


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_canonical_recycle_bin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "clean my recycle bin when it reaches 80%"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "threshold"
        assert data["trigger"]["params"]["threshold"] == 80
        assert data["action"]["name"] == "empty_recycle_bin"


@pytest.mark.asyncio
async def test_canonical_email_friday():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "email me a summary every Friday at 5pm"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "time"
        assert data["trigger"]["params"]["cron"] == "0 17 * * 5"
        assert data["action"]["name"] == "send_email"


@pytest.mark.asyncio
async def test_varied_disk_threshold():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "notify me if disk usage goes over 90%"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "threshold"
        assert data["trigger"]["params"]["threshold"] == 90
        assert data["action"]["name"] == "write_log_notification"


@pytest.mark.asyncio
async def test_varied_ambiguity_recycle_bin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "clean the recycle bin when it is full"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "threshold"
        assert len(data["ambiguities"]) > 0
        assert data["ambiguities"][0]["field_path"] == "trigger.params.threshold"


@pytest.mark.asyncio
async def test_varied_webhook():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "send webhook every day"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "time"
        assert data["action"]["name"] == "send_webhook"


@pytest.mark.asyncio
async def test_varied_healthcheck():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "run healthcheck every 5 minutes"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "time"
        assert data["action"]["name"] == "run_http_healthcheck"


@pytest.mark.asyncio
async def test_varied_disk_85():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "alert me when disk usage reaches 85%"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["trigger"]["type"] == "threshold"
        assert data["trigger"]["params"]["threshold"] == 85


@pytest.mark.asyncio
async def test_empty_and_gibberish():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Empty
        resp_empty = await ac.post("/parse", json={"raw_text": "   "})
        assert resp_empty.status_code == 200
        assert resp_empty.json()["parseable"] is False

        # Gibberish
        resp_gib = await ac.post("/parse", json={"raw_text": "asdkjhf qwioeu 123897 !@#"})
        assert resp_gib.status_code == 200
        assert resp_gib.json()["parseable"] is False


@pytest.mark.asyncio
async def test_compound_sentence_rejection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/parse",
            json={"raw_text": "clean bin at 80% and email me weekly summary every Friday at 5pm"}
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"] == "compound_automation_rejected"
        assert "Please describe one automation at a time." in data["message"]
        assert data["detected_count"] >= 2


@pytest.mark.asyncio
async def test_simulated_gemini_429_failover_to_groq(monkeypatch):
    """
    Simulate Gemini raising 429 RateLimitError.
    Verify Groq provider is called and provider_failover audit event is written.
    """
    audit_events = []

    def mock_log_audit(event_type, payload, automation_id=None):
        audit_events.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr("app.providers.log_audit_event", mock_log_audit)

    class FailingGemini(LLMProvider):
        async def complete_structured(self, prompt, schema):
            raise RateLimitError("Gemini 429 quota exhausted")

    class SuccessfulGroq(LLMProvider):
        async def complete_structured(self, prompt, schema):
            return schema.model_validate({
                "raw_text": prompt,
                "detected_count": 1,
                "parseable": True,
                "trigger": {"type": "threshold", "params": {"metric": "recycle_bin_percentage", "threshold": 80, "comparator": ">="}},
                "action": {"name": "empty_recycle_bin", "params": {}},
                "ambiguities": []
            })

    test_chain = ProviderChain([FailingGemini(), SuccessfulGroq()])
    monkeypatch.setattr(main_module, "chain", test_chain)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/parse", json={"raw_text": "clean my recycle bin when it reaches 80%"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["parseable"] is True
        assert data["action"]["name"] == "empty_recycle_bin"

    # Verify audit event recorded provider_failover for Gemini
    assert any(
        e["event_type"] == "provider_failover" and e["payload"]["provider"] == "FailingGemini"
        for e in audit_events
    )
