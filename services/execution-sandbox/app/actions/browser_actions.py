from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
from .common import ActionResult, ActionNotAvailableError


class BrowserOpenUrlParams(BaseModel):
    url: str = Field(..., description="URL to open in managed isolated browser session")


class BrowserListTabsParams(BaseModel):
    pass


class BrowserCloseTabParams(BaseModel):
    tab_id: int = Field(..., description="Index or ID of tab to close")


class BrowserClearCacheParams(BaseModel):
    pass


async def _dispatch_browser_job(action_name: str, params_dict: dict) -> ActionResult:
    from ..db import create_host_agent_job, get_online_host_agent
    agent = get_online_host_agent()
    if not agent:
        raise ActionNotAvailableError("awaiting_host_agent: host-boundary action, requires active host agent")

    job_id = create_host_agent_job(
        host_agent_id=agent["id"],
        action_name=action_name,
        params=params_dict
    )
    return ActionResult(
        success=True,
        message=f"Dispatched {action_name} job {job_id} to host agent {agent['id']}",
        details={"job_id": job_id, "host_agent_id": agent["id"], "action": action_name, "status": "pending"}
    )


async def browser_open_url(params: BrowserOpenUrlParams) -> ActionResult:
    return await _dispatch_browser_job("browser_open_url", params.model_dump())


async def browser_list_open_tabs(params: BrowserListTabsParams) -> ActionResult:
    return await _dispatch_browser_job("browser_list_open_tabs", params.model_dump())


async def browser_close_tab(params: BrowserCloseTabParams) -> ActionResult:
    return await _dispatch_browser_job("browser_close_tab", params.model_dump())


async def browser_clear_managed_cache(params: BrowserClearCacheParams) -> ActionResult:
    return await _dispatch_browser_job("browser_clear_managed_cache", params.model_dump())
