from typing import Any, Callable, Dict, List, Tuple, Type
from pydantic import BaseModel, ValidationError

from .actions.common import ActionResult, ActionNotRegisteredError, ActionNotAvailableError
from .actions.send_email import SendEmailParams, send_email
from .actions.send_webhook import SendWebhookParams, send_webhook
from .actions.write_log_notification import WriteLogParams, write_log_notification
from .actions.run_http_healthcheck import HealthcheckParams, run_http_healthcheck
from .actions.empty_trash import EmptyTrashParams, empty_trash
from .actions.empty_recycle_bin import EmptyRecycleBinParams, empty_recycle_bin
from .actions.web_search import WebSearchParams, web_search
from .actions.check_disk_usage import CheckDiskUsageParams, check_disk_usage
from .actions.list_drives import ListDrivesParams, list_drives
from .actions.clean_temp_and_cache import CleanTempAndCacheParams, clean_temp_and_cache
from .actions.delete_path import DeletePathParams, delete_path
from .actions.get_memory_usage import EmptyParams as MemoryParams, get_memory_usage
from .actions.list_top_processes import ListProcessesParams, list_top_processes
from .actions.list_connected_devices import EmptyParams as DeviceParams, list_connected_devices
from .actions.browser_actions import (
    BrowserOpenUrlParams, browser_open_url,
    BrowserListTabsParams, browser_list_open_tabs,
    BrowserCloseTabParams, browser_close_tab,
    BrowserClearCacheParams, browser_clear_managed_cache,
)

REGISTRY: Dict[str, Tuple[Type[BaseModel], Callable]] = {
    "send_email": (SendEmailParams, send_email),
    "send_webhook": (SendWebhookParams, send_webhook),
    "write_log_notification": (WriteLogParams, write_log_notification),
    "run_http_healthcheck": (HealthcheckParams, run_http_healthcheck),
    "empty_trash": (EmptyTrashParams, empty_trash),
    "empty_recycle_bin": (EmptyRecycleBinParams, empty_recycle_bin),  # Deprecated alias
    "web_search": (WebSearchParams, web_search),
    "check_disk_usage": (CheckDiskUsageParams, check_disk_usage),
    "list_drives": (ListDrivesParams, list_drives),
    "get_memory_usage": (MemoryParams, get_memory_usage),
    "list_top_processes": (ListProcessesParams, list_top_processes),
    "list_connected_devices": (DeviceParams, list_connected_devices),
    "clean_temp_and_cache": (CleanTempAndCacheParams, clean_temp_and_cache),
    "delete_path": (DeletePathParams, delete_path),
    "browser_open_url": (BrowserOpenUrlParams, browser_open_url),
    "browser_list_open_tabs": (BrowserListTabsParams, browser_list_open_tabs),
    "browser_close_tab": (BrowserCloseTabParams, browser_close_tab),
    "browser_clear_managed_cache": (BrowserClearCacheParams, browser_clear_managed_cache),
}

ACTION_DESCRIPTIONS: Dict[str, str] = {
    "send_email": "Dispatches an email notification to a specified recipient with subject and body.",
    "send_webhook": "Sends an HTTP webhook payload to a designated URL.",
    "write_log_notification": "Records an application log notification at info, warning, or error level.",
    "run_http_healthcheck": "Checks the HTTP response status of a target endpoint against expected status code.",
    "empty_trash": "Triggers Trash / Recycle Bin cleanup via host agent.",
    "empty_recycle_bin": "Deprecated alias for empty_trash.",
    "web_search": "Controlled, rate-limited, read-only web search.",
    "check_disk_usage": "Checks capacity and free space on host drive letter or mount point.",
    "list_drives": "Lists available host logical drives and mount points.",
    "get_memory_usage": "Checks host RAM percentage and memory metrics via psutil.",
    "list_top_processes": "Lists host top processes sorted by memory or CPU usage.",
    "list_connected_devices": "Enumerates connected USB and HID hardware devices on host.",
    "clean_temp_and_cache": "Cleans curated safe temporary locations and user cache folders.",
    "delete_path": "High-risk deletion of arbitrary user-specified path subject to strict denylist.",
    "browser_open_url": "Opens a URL in a separate, isolated managed browser session.",
    "browser_list_open_tabs": "Lists open tabs within the managed browser session.",
    "browser_close_tab": "Closes a tab within the managed browser session.",
    "browser_clear_managed_cache": "Clears cache and storage of the managed browser session.",
}


def get_mcp_tools() -> List[Dict[str, Any]]:
    tools = []
    for name, (schema, _) in REGISTRY.items():
        tools.append({
            "name": name,
            "description": ACTION_DESCRIPTIONS.get(name, f"Executes {name} action"),
            "inputSchema": schema.model_json_schema()
        })
    return tools


async def invoke(action_name: str, raw_params: Dict[str, Any]) -> ActionResult:
    if action_name not in REGISTRY:
        raise ActionNotRegisteredError(action_name)
    schema, fn = REGISTRY[action_name]
    # Pydantic validation error will raise ValidationError -> handled as 400
    validated = schema(**raw_params)
    return await fn(validated)
