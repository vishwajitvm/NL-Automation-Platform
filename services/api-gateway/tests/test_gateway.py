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
async def test_create_automation_content_policy_blocked():
    """Illicit content blocked at router pre-gate without reaching intent parser"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "where can I buy drugs online?"})
        assert resp.status_code == 400
        err = resp.json()["detail"]
        assert err["error"] == "content_policy_blocked"
        assert "controlled substances" in err["message"] or "SAMHSA" in err["message"]


@pytest.mark.asyncio
async def test_create_automation_hard_denylist_refusal():
    """Drive root deletion blocked at hard denylist before confirmation is offered"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "delete C:\\ drive"})
        assert resp.status_code == 400
        err = resp.json()["detail"]
        assert err["error"] == "FORBIDDEN_DELETION"
        assert "I can't delete an entire drive" in err["message"]


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
    """Low-risk happy path creates active automation"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "email me a summary every Friday at 5pm"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["status"] == "active"
        assert "id" in data


@pytest.mark.asyncio
async def test_create_automation_ambiguity_round_trip():
    """Ambiguity flow pauses at draft, resumes on user response"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: ambiguous request
        resp1 = await ac.post("/api/v1/automations", json={"text": "clean the recycle bin when it is full"})
        assert resp1.status_code in (200, 201)
        data1 = resp1.json()
        assert data1["status"] == "draft"
        auto_id = data1["id"]
        assert "clarification_prompt" in data1

        # Step 2: resume with clarification
        resp2 = await ac.post(f"/api/v1/automations/{auto_id}/resume", json={"user_response": "when it reaches 80%"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["id"] == auto_id


@pytest.mark.asyncio
async def test_execute_immediate_command():
    """One-off command executes with trigger.type = immediate"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/commands", json={"text": "search for python async tutorials"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("executed", "active")
        assert "id" in data


@pytest.mark.asyncio
async def test_list_and_audit_endpoints():
    """List automations and audit logs"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp_list = await ac.get("/api/v1/automations")
        assert resp_list.status_code == 200
        assert "automations" in resp_list.json()

        resp_audit = await ac.get("/api/v1/audit")
        assert resp_audit.status_code == 200
        assert "audit_logs" in resp_audit.json()


@pytest.mark.asyncio
async def test_credential_refusal_fixed_wording():
    """Credential query returns exact fixed refusal wording from §10.6"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "what's my wifi password"})
        assert resp.status_code == 400
        err = resp.json()["detail"]
        assert err["message"] == "I'm sorry, but this information is not allowed to be shared — we cannot share system credentials with anyone."


@pytest.mark.asyncio
async def test_hard_denylist_short_circuits_before_guardrail(monkeypatch):
    """Step 4 hard denylist short-circuits before guardrail or ethics calls"""
    called_guardrail = False

    async def mock_post(client, url, *args, **kwargs):
        nonlocal called_guardrail
        if "classify" in str(url) or "ethics-review" in str(url):
            called_guardrail = True
        return await original_post(client, url, *args, **kwargs)

    import httpx
    original_post = httpx.AsyncClient.post
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "delete C:\\Windows"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "FORBIDDEN_DELETION"
        # Assert guardrail & ethics were NEVER invoked!
        assert called_guardrail is False


@pytest.mark.asyncio
async def test_informational_query_system_memory():
    """Informational query executes low-risk diagnostic action with zero false block"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "what is my current memory usage"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("lane") == "informational_query"
        assert data.get("status") == "executed"
        assert data.get("action") in ("get_memory_usage", "list_top_processes")
        assert "result" in data


@pytest.mark.asyncio
async def test_informational_query_connected_devices():
    """Informational query lists connected devices directly"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "how many external devices are connected to my device"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("lane") == "informational_query"
        assert data.get("status") == "executed"
        assert data.get("action") == "list_connected_devices"
        assert "result" in data


@pytest.mark.asyncio
async def test_delayed_reminder_plan():
    """Relative delay reminders produce trigger.type = 'delay' and write_log_notification"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "remind me to stretch after 5 minutes"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        plan = data.get("plan", {})
        assert plan.get("trigger", {}).get("type") == "delay"
        assert plan.get("trigger", {}).get("params", {}).get("delay_seconds") == 300
        assert plan.get("action", {}).get("name") == "write_log_notification"


@pytest.mark.asyncio
async def test_recycle_bin_immediate_never_80():
    """'please clean my recycle bin' runs immediate, never defaulting to 80%"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/automations", json={"text": "please clean my recycle bin"})
        assert resp.status_code in (200, 201)
        data = resp.json()
        plan = data.get("plan", {})
        assert plan.get("trigger", {}).get("type") == "immediate"
        assert plan.get("action", {}).get("name") in ("empty_trash", "empty_recycle_bin")
        # Ensure 80% was NOT invented
        assert plan.get("trigger", {}).get("params", {}).get("threshold") != 80
