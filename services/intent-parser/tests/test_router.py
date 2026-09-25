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
