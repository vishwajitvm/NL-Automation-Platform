import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger("managed-browser")


class ManagedBrowserSession:
    """
    Dedicated, isolated managed browser session (Playwright + Chromium).
    Operates with its own sandboxed profile directory completely separate from the user's
    personal Chrome/Firefox/Edge profiles, saved credentials, cookies, and live browsing tabs.
    """

    def __init__(self, profile_dir: Optional[str] = None):
        self.profile_dir = profile_dir or os.path.join(tempfile.gettempdir(), "nl_automation_managed_browser_profile")
        os.makedirs(self.profile_dir, exist_ok=True)
        self.tabs: List[Dict[str, Any]] = []
        self._next_tab_id = 1
        self._playwright = None
        self._context = None

    async def open_url(self, url: str) -> Dict[str, Any]:
        tab_id = self._next_tab_id
        self._next_tab_id += 1
        tab_info = {"id": tab_id, "url": url, "title": f"Tab {tab_id}: {url}"}

        # Attempt to launch Playwright persistent context in isolated profile dir
        try:
            from playwright.async_api import async_playwright
            if not self._playwright:
                self._playwright = await async_playwright().start()
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=self.profile_dir,
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
            page = await self._context.new_page()
            await page.goto(url, timeout=10000)
            page_title = await page.title()
            if page_title:
                tab_info["title"] = page_title
            tab_info["page_ref"] = page
        except Exception as e:
            logger.info(f"Playwright isolated launch fallback (tracked mode): {e}")

        self.tabs.append(tab_info)
        return {"tab_id": tab_id, "url": url, "title": tab_info["title"]}

    async def list_tabs(self) -> List[Dict[str, Any]]:
        return [{"id": t["id"], "url": t["url"], "title": t.get("title", t["url"])} for t in self.tabs]

    async def close_tab(self, tab_id: int) -> bool:
        for i, t in enumerate(self.tabs):
            if t["id"] == tab_id:
                if "page_ref" in t:
                    try:
                        await t["page_ref"].close()
                    except Exception:
                        pass
                self.tabs.pop(i)
                return True
        return False

    async def clear_cache(self) -> Dict[str, Any]:
        closed_count = len(self.tabs)
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self.tabs.clear()

        # Remove profile cache directory and recreate clean directory
        if os.path.exists(self.profile_dir):
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
                os.makedirs(self.profile_dir, exist_ok=True)
            except Exception as e:
                logger.warning(f"Error purging profile dir: {e}")

        return {
            "tabs_closed": closed_count,
            "cache_cleared": True,
            "profile_dir": self.profile_dir
        }
