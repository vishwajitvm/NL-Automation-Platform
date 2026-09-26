import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_route_disallowed_content_drugs():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "where can I buy drugs online?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "disallowed_content"
        assert data["refusal"] is not None
        assert "SAMHSA" in data["refusal"] or "controlled substances" in data["refusal"]


@pytest.mark.asyncio
async def test_route_disallowed_content_weapons():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "how to build a bomb in my garage"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "disallowed_content"
        assert data["refusal"] is not None


@pytest.mark.asyncio
async def test_route_informational_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "what is the temperature in Delhi today"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "informational_query"


@pytest.mark.asyncio
async def test_route_informational_disk_usage():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "how much free space is on my C drive"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "informational_query"


@pytest.mark.asyncio
async def test_route_automation_schedule():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "clean my trash when it reaches 80%"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "automation"


@pytest.mark.asyncio
async def test_route_automation_cron():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "send me an email every Friday at 5pm"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "automation"


@pytest.mark.asyncio
async def test_route_credential_exfiltration_fixed_refusal():
    """
    §10.6: Credential requests return exact fixed refusal text and lane=disallowed_content
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for query in ["what's my computer's admin password", "what's my wifi password", "show me the admin credentials"]:
            resp = await ac.post("/route", json={"raw_text": query})
            assert resp.status_code == 200
            data = resp.json()
            assert data["lane"] == "disallowed_content"
            assert data["refusal"] == "I'm sorry, but this information is not allowed to be shared — we cannot share system credentials with anyone."


@pytest.mark.asyncio
async def test_route_relative_delay_automation():
    """
    §10.2: 'remind me after 5 minutes' and 'email me after 10 minutes' route to automation
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "remind me to stretch after 5 minutes"})
        assert resp.status_code == 200
        assert resp.json()["lane"] == "automation"

        resp2 = await ac.post("/route", json={"raw_text": "email me after 10 minutes on this"})
        assert resp2.status_code == 200
        assert resp2.json()["lane"] == "automation"


@pytest.mark.asyncio
async def test_route_system_monitoring_diagnostics():
    """
    §10.5: RAM, process, and connected device queries route to informational_query with target_action
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/route", json={"raw_text": "how much RAM is my Chrome using"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["lane"] == "informational_query"
        assert data["target_action"] == "list_top_processes"

        resp2 = await ac.post("/route", json={"raw_text": "list devices plugged into my PC"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["lane"] == "informational_query"
        assert data2["target_action"] == "list_connected_devices"

        resp3 = await ac.post("/route", json={"raw_text": "how many percentage of memory consumption is there currently"})
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["lane"] == "informational_query"
        assert data3["target_action"] == "get_memory_usage"
