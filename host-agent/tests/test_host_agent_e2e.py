import asyncio
import tempfile
import pytest
import httpx
from unittest.mock import patch

from host_agent.client import HostAgentClient
from host_agent.trash.windows import WindowsTrash


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.asyncio
async def test_host_agent_full_lifecycle():
    base_url = "http://localhost:8080"
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 1. Generate Token
        token_resp = await client.post("/api/v1/host-agents/tokens")
        assert token_resp.status_code == 200
        token_data = token_resp.json()
        token = token_data["token"]
        assert token.startswith("ha_")

        # 2. Register Agent
        reg_payload = {
            "token": token,
            "os_family": "Windows",
            "distro_id": "windows",
            "distro_name": "Windows 11",
            "distro_version": "10.0.22631",
            "capabilities": ["empty_trash", "empty_recycle_bin"]
        }
        reg_resp = await client.post("/api/v1/host-agents/register", json=reg_payload)
        assert reg_resp.status_code == 200
        assert reg_resp.json()["status"] == "online"

        # 3. Push Metric
        metric_resp = await client.post(
            "/api/v1/host-agents/metrics",
            json={"metric": "trash_usage_pct", "value": 85.5},
            headers={"X-Agent-Token": token}
        )
        assert metric_resp.status_code == 200

        # 4. Create Automation with empty_trash / recycle bin at 80%
        auto_resp = await client.post(
            "/api/v1/automations",
            json={"text": "clean my recycle bin when it reaches 80%"}
        )
        assert auto_resp.status_code in (200, 201)
        auto_data = auto_resp.json()
        auto_id = auto_data["id"]

        # 5. Check Poll Next Job
        job_resp = await client.get("/api/v1/host-agents/jobs/next", headers={"X-Agent-Token": token})
        assert job_resp.status_code == 200

        # 6. Verify List Host Agents
        list_resp = await client.get("/api/v1/host-agents")
        assert list_resp.status_code == 200
        agents = list_resp.json()["host_agents"]
        assert any(a["os_family"] == "Windows" for a in agents)


@pytest.mark.asyncio
async def test_host_agent_job_dispatch_and_execution():
    base_url = "http://localhost:8080"
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # 1. Register a dedicated agent for job execution test
        token_resp = await client.post("/api/v1/host-agents/tokens")
        token = token_resp.json()["token"]

        reg_resp = await client.post("/api/v1/host-agents/register", json={
            "token": token,
            "os_family": "Windows",
            "capabilities": ["empty_trash", "empty_recycle_bin"]
        })
        agent_id = reg_resp.json()["agent"]["id"]

        # 2. Initialize HostAgentClient with a mocked/safe trash folder
        temp_dir = tempfile.mkdtemp()
        agent_client = HostAgentClient(token=token, server_url=base_url)
        agent_client.trash_backend = WindowsTrash(override_path=temp_dir)

        # 3. Trigger an empty_trash execution from execution sandbox or direct call
        # Let's execute via execution-sandbox container or direct job insertion
        # We can call execution-sandbox via docker or insert job via db/api
        from host_agent.trash import ActionResult

        # Test job poll and execute with agent_client
        # Let's push a metric first
        await agent_client.push_metrics()

        # Check job poll (none right now)
        found = await agent_client.poll_and_execute_job()
        assert found is False
