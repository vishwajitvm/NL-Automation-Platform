import os
import platform
import shutil
from typing import Any, Dict


def detect() -> Dict[str, Any]:
    system = platform.system()  # "Windows" | "Linux" | "Darwin"
    info: Dict[str, Any] = {"os_family": system}

    if system == "Linux":
        os_release = {}
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        os_release[k] = v.strip('"')
        except FileNotFoundError:
            pass
        info["distro_id"] = os_release.get("ID", "unknown")
        info["distro_name"] = os_release.get("NAME", "unknown")
        info["distro_version"] = os_release.get("VERSION_ID", "unknown")
        info["init_system"] = "systemd" if shutil.which("systemctl") else "other"
        for pm, binary in [
            ("apt", "apt-get"),
            ("dnf", "dnf"),
            ("yum", "yum"),
            ("pacman", "pacman"),
            ("apk", "apk"),
            ("zypper", "zypper"),
        ]:
            if shutil.which(binary):
                info["package_manager"] = pm
                break
        else:
            info["package_manager"] = "unknown"
        info["trash_path"] = os.path.expanduser("~/.local/share/Trash")

    elif system == "Windows":
        info["trash_path"] = "shell:RecycleBinFolder"
        info["distro_id"] = "windows"
        info["distro_name"] = f"Windows {platform.release()}"
        info["distro_version"] = platform.version()
        info["init_system"] = "service_control_manager"
        info["package_manager"] = "winget" if shutil.which("winget") else "unknown"

    elif system == "Darwin":
        info["trash_path"] = os.path.expanduser("~/.Trash")
        info["distro_id"] = "macos"
        info["distro_name"] = "macOS"
        try:
            info["distro_version"] = platform.mac_ver()[0]
        except Exception:
            info["distro_version"] = "unknown"
        info["init_system"] = "launchd"
        info["package_manager"] = "brew" if shutil.which("brew") else "unknown"

    else:
        info["os_family"] = "unsupported"

    return info
