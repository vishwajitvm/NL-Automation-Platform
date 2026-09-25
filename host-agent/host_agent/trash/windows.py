import ctypes
import os
import shutil
from typing import Any, Dict
from . import ActionResult, TrashBackend


class WindowsTrash(TrashBackend):
    def __init__(self, override_path: str = None):
        self.override_path = override_path

    def get_usage_pct(self) -> float:
        trash_bytes = 0
        if self.override_path and os.path.exists(self.override_path):
            for dirpath, _, filenames in os.walk(self.override_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        trash_bytes += os.path.getsize(fp)
                    except OSError:
                        pass
        else:
            try:
                class SHQUERYRBINFO(ctypes.Structure):
                    _fields_ = [
                        ('cbSize', ctypes.c_ulong),
                        ('i64Size', ctypes.c_int64),
                        ('i64NumItems', ctypes.c_int64),
                    ]
                rbinfo = SHQUERYRBINFO()
                rbinfo.cbSize = ctypes.sizeof(SHQUERYRBINFO)
                res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(rbinfo))
                if res == 0:
                    trash_bytes = rbinfo.i64Size
            except Exception:
                trash_bytes = 0

        home_drive = os.path.splitdrive(os.path.expanduser("~"))[0] or "C:"
        try:
            total_bytes, _, _ = shutil.disk_usage(home_drive + "\\")
        except Exception:
            total_bytes = 100 * 1024 * 1024 * 1024

        pct = (trash_bytes / max(total_bytes, 1)) * 100.0
        return round(pct, 2)

    def empty(self) -> ActionResult:
        if self.override_path and os.path.exists(self.override_path):
            count = 0
            for item in os.listdir(self.override_path):
                p = os.path.join(self.override_path, item)
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
                    count += 1
                except Exception as e:
                    return ActionResult(success=False, message=f"Error deleting {p}: {e}")
            return ActionResult(success=True, message=f"Recycle bin emptied ({count} items removed).")

        try:
            # Flags: SHERB_NOCONFIRMATION (0x1), SHERB_NOPROGRESSUI (0x2), SHERB_NOSOUND (0x4)
            flags = 0x00000001 | 0x00000002 | 0x00000004
            res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            if res == 0:
                return ActionResult(success=True, message="Recycle Bin emptied successfully on Windows.")
            else:
                return ActionResult(success=False, message=f"Windows SHEmptyRecycleBinW returned error code {res}")
        except Exception as e:
            return ActionResult(success=False, message=f"Permission or OS error emptying Windows Recycle Bin: {e}")
