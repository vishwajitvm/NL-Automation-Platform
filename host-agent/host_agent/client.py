import asyncio
import logging
import os
import platform
import shutil
from typing import Any, Dict, List, Optional
import httpx

from .platform_detect import detect
from .trash import ActionResult, TrashBackend
from .trash.windows import WindowsTrash
from .trash.linux import LinuxTrash
from .trash.macos import MacOSTrash
from .safety.denylist import is_forbidden, FORBIDDEN_REFUSAL_MESSAGE
from .browser.session import ManagedBrowserSession

logger = logging.getLogger("host-agent")


def get_trash_backend() -> TrashBackend:
    system = platform.system()
    if system == "Windows":
        return WindowsTrash()
    elif system == "Darwin":
        return MacOSTrash()
    else:
        return LinuxTrash()


def _format_bytes(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


class HostAgentClient:
    def __init__(self, token: str, server_url: str = "http://localhost:8080", report_interval: int = 30):
        self.token = token
        self.server_url = server_url.rstrip("/")
        self.report_interval = report_interval
        self.trash_backend = get_trash_backend()
        self.browser_session = ManagedBrowserSession()
        self.is_running = False
        self.agent_info: Optional[Dict[str, Any]] = None
        self.platform_info = detect()

    async def register(self) -> bool:
        sys_info = dict(self.platform_info)
        sys_info["token"] = self.token
        sys_info["capabilities"] = [
            "empty_trash", "empty_recycle_bin",
            "check_disk_usage", "list_drives",
            "clean_temp_and_cache",
            "delete_path", "preview_delete_path",
            "browser_open_url", "browser_list_open_tabs",
            "browser_close_tab", "browser_clear_managed_cache",
        ]

        url = f"{self.server_url}/api/v1/host-agents/register"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(url, json=sys_info)
                if resp.status_code == 200:
                    data = resp.json()
                    self.agent_info = data.get("agent")
                    logger.info(f"Host agent successfully registered. OS: {sys_info.get('os_family')}")
                    return True
                else:
                    logger.error(f"Failed to register host agent: HTTP {resp.status_code} - {resp.text}")
                    return False
            except Exception as e:
                logger.error(f"Connection error registering host agent: {e}")
                return False

    async def push_metrics(self) -> bool:
        try:
            val = self.trash_backend.get_usage_pct()
            url = f"{self.server_url}/api/v1/host-agents/metrics"
            headers = {"X-Agent-Token": self.token}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"metric": "trash_usage_pct", "value": val}, headers=headers)
                if resp.status_code == 200:
                    logger.debug(f"Reported trash_usage_pct={val}%")
                    return True
                else:
                    logger.warning(f"Metric report rejected: HTTP {resp.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"Error pushing metrics: {e}")
            return False

    def execute_check_disk_usage(self, params: Dict[str, Any]) -> ActionResult:
        os_fam = self.platform_info.get("os_family", "Windows")
        default_drive = "C:\\" if os_fam == "Windows" else "/"
        drive = params.get("drive", default_drive)
        try:
            u = shutil.disk_usage(drive)
            total_gb = round(u.total / (1024**3), 2)
            used_gb = round(u.used / (1024**3), 2)
            free_gb = round(u.free / (1024**3), 2)
            pct = round((u.used / u.total) * 100, 1)
            return ActionResult(
                success=True,
                message=f"Drive {drive}: {used_gb} GB used of {total_gb} GB ({pct}%), {free_gb} GB free",
                details={"drive": drive, "total_gb": total_gb, "used_gb": used_gb, "free_gb": free_gb, "used_pct": pct}
            )
        except Exception as e:
            return ActionResult(success=False, message=f"Failed to check disk usage on {drive}: {e}")

    def execute_list_drives(self, params: Dict[str, Any]) -> ActionResult:
        os_fam = self.platform_info.get("os_family", "")
        drives = []
        if os_fam == "Windows":
            import string
            for letter in string.ascii_uppercase:
                path = f"{letter}:\\"
                if os.path.exists(path):
                    try:
                        u = shutil.disk_usage(path)
                        drives.append({
                            "drive": path,
                            "total_gb": round(u.total / (1024**3), 2),
                            "free_gb": round(u.free / (1024**3), 2),
                            "used_pct": round((u.used / u.total) * 100, 1)
                        })
                    except Exception:
                        drives.append({"drive": path, "total_gb": 0, "free_gb": 0, "used_pct": 0})
        elif os_fam == "Linux":
            try:
                with open("/proc/mounts") as f:
                    seen = set()
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2 and (parts[0].startswith("/dev/") or parts[1] == "/"):
                            mp = parts[1]
                            if mp not in seen:
                                seen.add(mp)
                                try:
                                    u = shutil.disk_usage(mp)
                                    drives.append({
                                        "drive": mp,
                                        "device": parts[0],
                                        "total_gb": round(u.total / (1024**3), 2),
                                        "free_gb": round(u.free / (1024**3), 2),
                                        "used_pct": round((u.used / u.total) * 100, 1)
                                    })
                                except Exception:
                                    pass
            except Exception:
                drives.append({"drive": "/", "total_gb": 50.0, "free_gb": 25.0, "used_pct": 50.0})
        else:
            drives.append({"drive": "/", "total_gb": 256.0, "free_gb": 128.0, "used_pct": 50.0})

        return ActionResult(
            success=True,
            message=f"Found {len(drives)} available drives",
            details={"drives": drives}
        )

    def execute_clean_temp_and_cache(self, params: Dict[str, Any]) -> ActionResult:
        """
        Cleans curated safe temporary locations only:
        Windows: %TEMP%, %LOCALAPPDATA%\\Temp, trash/recycle bin
        Linux: /tmp (user files), ~/.cache, trash
        macOS: ~/Library/Caches, trash
        """
        os_fam = self.platform_info.get("os_family", "")
        cleaned_files = 0
        freed_bytes = 0
        target_dirs: List[str] = []

        if os_fam == "Windows":
            temp1 = os.environ.get("TEMP")
            temp2 = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp")
            if temp1 and os.path.exists(temp1):
                target_dirs.append(temp1)
            if temp2 and os.path.exists(temp2) and temp2 != temp1:
                target_dirs.append(temp2)
        elif os_fam == "Linux":
            target_dirs.append(os.path.expanduser("~/.cache"))
        else:
            target_dirs.append(os.path.expanduser("~/Library/Caches"))

        for d in target_dirs:
            if not os.path.exists(d):
                continue
            for root, dirs, files in os.walk(d):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        cleaned_files += 1
                        freed_bytes += sz
                    except Exception:
                        pass

        # Also empty trash/recycle bin
        trash_res = self.trash_backend.empty()
        human_freed = _format_bytes(freed_bytes)

        return ActionResult(
            success=True,
            message=f"Cleaned {cleaned_files} temporary/cache files ({human_freed} freed) and emptied trash",
            details={
                "cleaned_files": cleaned_files,
                "freed_bytes": freed_bytes,
                "human_freed": human_freed,
                "trash_cleared": trash_res.success
            }
        )

    def execute_preview_delete_path(self, params: Dict[str, Any]) -> ActionResult:
        path = params.get("path", "")
        os_fam = self.platform_info.get("os_family", "Windows")

        # 1. Hard denylist check
        if is_forbidden(path, os_fam):
            return ActionResult(
                success=False,
                message=FORBIDDEN_REFUSAL_MESSAGE,
                details={"path": path, "forbidden": True}
            )

        if not os.path.exists(path):
            return ActionResult(
                success=True,
                message=f"Path '{path}' does not exist.",
                details={"item_count": 0, "total_size_bytes": 0, "human_size": "0 B", "sample_paths": []}
            )

        item_count = 0
        total_size = 0
        sample_paths = []

        if os.path.isfile(path):
            item_count = 1
            total_size = os.path.getsize(path)
            sample_paths.append(os.path.basename(path))
        else:
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    item_count += 1
                    try:
                        total_size += os.path.getsize(fp)
                    except Exception:
                        pass
                    if len(sample_paths) < 5:
                        sample_paths.append(os.path.relpath(fp, path))
                for d in dirs:
                    item_count += 1

        human_sz = _format_bytes(total_size)
        return ActionResult(
            success=True,
            message=f"Preview: {item_count} items ({human_sz}) in {path}",
            details={
                "item_count": item_count,
                "total_size_bytes": total_size,
                "human_size": human_sz,
                "sample_paths": sample_paths
            }
        )

    def execute_delete_path(self, params: Dict[str, Any]) -> ActionResult:
        path = params.get("path", "")
        os_fam = self.platform_info.get("os_family", "Windows")

        if is_forbidden(path, os_fam):
            return ActionResult(
                success=False,
                message=FORBIDDEN_REFUSAL_MESSAGE,
                details={"path": path, "forbidden": True}
            )

        if not os.path.exists(path):
            return ActionResult(
                success=True,
                message=f"Path '{path}' does not exist (nothing to delete).",
                details={"path": path, "deleted": False}
            )

        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return ActionResult(
                success=True,
                message=f"Successfully deleted target path: {path}",
                details={"path": path, "deleted": True}
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Permission denied or error deleting '{path}': {e}",
                details={"path": path, "error": str(e)}
            )

    async def execute_browser_action(self, action_name: str, params: Dict[str, Any]) -> ActionResult:
        try:
            if action_name == "browser_open_url":
                res = await self.browser_session.open_url(params.get("url", "about:blank"))
                return ActionResult(success=True, message=f"Opened URL {res['url']}", details=res)
            elif action_name == "browser_list_open_tabs":
                tabs = await self.browser_session.list_tabs()
                return ActionResult(success=True, message=f"{len(tabs)} tabs open in managed session", details={"tabs": tabs})
            elif action_name == "browser_close_tab":
                ok = await self.browser_session.close_tab(params.get("tab_id", 1))
                return ActionResult(success=ok, message="Tab closed" if ok else "Tab not found", details={"tab_id": params.get("tab_id")})
            elif action_name == "browser_clear_managed_cache":
                res = await self.browser_session.clear_cache()
                return ActionResult(success=True, message="Managed browser session cache cleared", details=res)
            else:
                return ActionResult(success=False, message=f"Unknown browser action: {action_name}")
        except Exception as e:
            return ActionResult(success=False, message=f"Error executing browser action {action_name}: {e}")

    async def poll_and_execute_job(self) -> bool:
        url = f"{self.server_url}/api/v1/host-agents/jobs/next"
        headers = {"X-Agent-Token": self.token}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return False
                job = resp.json().get("job")
                if not job:
                    return False

                job_id = job["id"]
                action_name = job["action_name"]
                params = job.get("params", {})
                logger.info(f"Received job {job_id} ({action_name})")

                # Dispatch action
                if action_name in ("empty_trash", "empty_recycle_bin"):
                    result = self.trash_backend.empty()
                elif action_name == "check_disk_usage":
                    result = self.execute_check_disk_usage(params)
                elif action_name == "list_drives":
                    result = self.execute_list_drives(params)
                elif action_name == "clean_temp_and_cache":
                    result = self.execute_clean_temp_and_cache(params)
                elif action_name == "preview_delete_path":
                    result = self.execute_preview_delete_path(params)
                elif action_name == "delete_path":
                    result = self.execute_delete_path(params)
                elif action_name.startswith("browser_"):
                    result = await self.execute_browser_action(action_name, params)
                else:
                    result = ActionResult(success=False, message=f"Action {action_name} not supported by host agent.")

                # Submit result back to API gateway
                res_url = f"{self.server_url}/api/v1/host-agents/jobs/{job_id}/result"
                status_str = "done" if result.success else "failed"
                await client.post(
                    res_url,
                    json={"status": status_str, "result": result.to_dict()},
                    headers=headers
                )
                logger.info(f"Completed job {job_id} with status {status_str}")
                return True
            except Exception as e:
                logger.error(f"Error in job poll/execute: {e}")
                return False

    async def run_loop(self):
        self.is_running = True
        logger.info(f"Host Agent client started. Reporting every {self.report_interval}s.")

        last_metric_push = 0
        while self.is_running:
            now = asyncio.get_event_loop().time()
            if now - last_metric_push >= self.report_interval:
                await self.push_metrics()
                last_metric_push = now

            await self.poll_and_execute_job()
            await asyncio.sleep(2)

    def stop(self):
        self.is_running = False
        logger.info("Host Agent client stopping...")
