import os
import shutil
import tempfile
import pytest
from host_agent.client import HostAgentClient, ActionResult
from host_agent.safety.denylist import FORBIDDEN_REFUSAL_MESSAGE


@pytest.fixture
def client():
    return HostAgentClient(token="test_token", server_url="http://localhost:8080")


def test_check_disk_usage(client):
    res = client.execute_check_disk_usage({})
    assert res.success is True
    assert "total_gb" in res.details
    assert "used_pct" in res.details
    assert res.details["total_gb"] > 0


def test_list_drives(client):
    res = client.execute_list_drives({})
    assert res.success is True
    assert "drives" in res.details
    assert len(res.details["drives"]) >= 1


def test_clean_temp_and_cache(client, monkeypatch):
    test_temp = tempfile.mkdtemp(prefix="nl_test_cache_")
    test_file = os.path.join(test_temp, "dummy.tmp")
    with open(test_file, "w") as f:
        f.write("hello world" * 100)

    monkeypatch.setenv("TEMP", test_temp)
    monkeypatch.setenv("LOCALAPPDATA", test_temp)
    try:
        res = client.execute_clean_temp_and_cache({})
        assert res.success is True
        assert res.details["cleaned_files"] >= 1
        assert not os.path.exists(test_file)
    finally:
        shutil.rmtree(test_temp, ignore_errors=True)


def test_preview_delete_path_forbidden(client):
    res = client.execute_preview_delete_path({"path": "C:\\Windows"})
    assert res.success is False
    assert res.message == FORBIDDEN_REFUSAL_MESSAGE
    assert res.details.get("forbidden") is True


def test_preview_delete_path_valid(client):
    test_dir = tempfile.mkdtemp(prefix="nl_test_preview_")
    for i in range(3):
        with open(os.path.join(test_dir, f"file_{i}.txt"), "w") as f:
            f.write(f"data {i}")

    try:
        res = client.execute_preview_delete_path({"path": test_dir})
        assert res.success is True
        assert res.details["item_count"] == 3
        assert len(res.details["sample_paths"]) == 3
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_delete_path_forbidden(client):
    res = client.execute_delete_path({"path": "C:\\"})
    assert res.success is False
    assert res.message == FORBIDDEN_REFUSAL_MESSAGE


def test_delete_path_valid(client):
    test_dir = tempfile.mkdtemp(prefix="nl_test_del_")
    dummy = os.path.join(test_dir, "data.txt")
    with open(dummy, "w") as f:
        f.write("delete me")

    assert os.path.exists(test_dir)
    res = client.execute_delete_path({"path": test_dir})
    assert res.success is True
    assert not os.path.exists(test_dir)


@pytest.mark.asyncio
async def test_managed_browser_control(client):
    # 1. Open URL
    res_open = await client.execute_browser_action("browser_open_url", {"url": "about:blank"})
    assert res_open.success is True
    tab_id = res_open.details["tab_id"]

    # 2. List tabs
    res_list = await client.execute_browser_action("browser_list_open_tabs", {})
    assert res_list.success is True
    assert len(res_list.details["tabs"]) == 1

    # 3. Close tab
    res_close = await client.execute_browser_action("browser_close_tab", {"tab_id": tab_id})
    assert res_close.success is True

    # 4. Clear cache
    res_cache = await client.execute_browser_action("browser_clear_managed_cache", {})
    assert res_cache.success is True
    assert res_cache.details["cache_cleared"] is True
