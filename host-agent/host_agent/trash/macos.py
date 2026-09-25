import os
import shutil
from typing import Any, Dict
from . import ActionResult, TrashBackend


class MacOSTrash(TrashBackend):
    def __init__(self, trash_path: str = None):
        self.trash_path = trash_path or os.path.expanduser("~/.Trash")

    def _get_trash_size_bytes(self) -> int:
        if not os.path.exists(self.trash_path):
            return 0
        total_size = 0
        for dirpath, _, filenames in os.walk(self.trash_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    pass
        return total_size

    def get_usage_pct(self) -> float:
        trash_bytes = self._get_trash_size_bytes()
        home = os.path.expanduser("~")
        try:
            total_bytes, _, _ = shutil.disk_usage(home)
        except Exception:
            total_bytes = 100 * 1024 * 1024 * 1024
        pct = (trash_bytes / max(total_bytes, 1)) * 100.0
        return round(pct, 2)

    def empty(self) -> ActionResult:
        if not os.path.exists(self.trash_path):
            return ActionResult(success=True, message="macOS Trash is already empty.")
        deleted_count = 0
        try:
            for entry in os.listdir(self.trash_path):
                entry_path = os.path.join(self.trash_path, entry)
                try:
                    if os.path.isdir(entry_path) and not os.path.islink(entry_path):
                        shutil.rmtree(entry_path)
                    else:
                        os.remove(entry_path)
                    deleted_count += 1
                except PermissionError as pe:
                    return ActionResult(success=False, message=f"Permission denied deleting {entry_path}: {pe}")
            return ActionResult(success=True, message=f"macOS Trash emptied successfully ({deleted_count} entries removed).")
        except Exception as e:
            return ActionResult(success=False, message=f"Error emptying macOS Trash: {e}")
