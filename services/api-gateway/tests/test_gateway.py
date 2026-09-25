import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_api_gateway_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_automation_empty_text():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "   "})
        assert resp.status_code == 400
        assert "I couldn't understand that." in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_automation_compound_rejected(monkeypatch):
    """Compound automation gets rejected with HTTP 422"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "clean bin at 80% and email me weekly"})
        assert resp.status_code == 422
        assert "Please describe one automation at a time." in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_automation_guardrail_blocked():
    """Destructive automation gets blocked with HTTP 400 and GUARDRAIL_BLOCKED"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "format C: drive every night"})
        assert resp.status_code == 400
        err = resp.json()["detail"]
        assert err["error"] == "GUARDRAIL_BLOCKED"
        assert "suggested_alternative" in err


@pytest.mark.asyncio
async def test_create_automation_unambiguous_happy_path():
    """Happy path creates active automation"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "clean my recycle bin when it reaches 80%"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "active"
        assert "id" in data
        assert data["plan"]["action"]["name"] == "empty_recycle_bin"


@pytest.mark.asyncio
async def test_create_automation_ambiguity_round_trip():
    """Ambiguous automation returns draft status, then /resume activates it"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Create ambiguous
        resp1 = await ac.post("/api/v1/automations", json={"text": "clean the recycle bin when it is full"})
        assert resp1.status_code in (200, 201)
        data1 = resp1.json()
        assert data1["status"] == "draft"
        auto_id = data1["id"]
        assert "clarification_prompt" in data1

        # Step 2: Resume with answer
        resp2 = await ac.post(f"/api/v1/automations/{auto_id}/resume", json={"user_response": "clean it when it is 80% full"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "active"


@pytest.mark.asyncio
async def test_list_and_audit_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/automations")
        assert resp.status_code == 200
        assert "automations" in resp.json()

        resp_audit = await ac.get("/api/v1/audit")
        assert resp_audit.status_code == 200
        assert "audit_logs" in resp_audit.json()
