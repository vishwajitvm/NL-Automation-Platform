import os
import re
from typing import Tuple

WINDOWS_FORBIDDEN = [
    r"^[A-Za-z]:\\?$",                      # any bare drive root, e.g. C:\, D:\
    r"^[A-Za-z]:\\Windows(\\.*)?$",
    r"^[A-Za-z]:\\Program Files(\s\(x86\))?(\\.*)?$",
    r"^[A-Za-z]:\\ProgramData$",            # root only
    r"^[A-Za-z]:\\Users$",                  # root only — C:\Users\someone is fine
]

LINUX_FORBIDDEN = [
    "/", "/etc", "/usr", "/bin", "/sbin", "/boot", "/lib", "/lib64",
    "/root", "/var", "/sys", "/proc", "/dev", "/home"  # /home root only
]

MACOS_FORBIDDEN = [
    "/", "/System", "/Library", "/Applications", "/bin", "/usr", "/Users"  # /Users root only
]

FORBIDDEN_REFUSAL_MESSAGE = (
    "I can't delete an entire drive or a core system folder — that would make the system unusable "
    "and isn't recoverable. If you want to free up space, I can clean temp files and cache, "
    "empty trash, or delete a specific folder you name."
)


def is_forbidden(path: str, os_family: str = "Windows") -> bool:
    """
    Evaluates whether a target deletion path is forbidden.
    Resolves symlinks/junctions first (os.path.realpath) to close symlink escape loopholes.
    """
    if not path or not path.strip():
        return True

    clean_path = path.strip()
    os_family_lower = os_family.lower()

    if "linux" in os_family_lower:
        norm = clean_path.replace("\\", "/").rstrip("/")
        if not norm:
            norm = "/"
        if norm in LINUX_FORBIDDEN:
            return True
        if os.name != "nt":
            try:
                resolved = os.path.realpath(clean_path).rstrip("/")
                if not resolved:
                    resolved = "/"
                if resolved in LINUX_FORBIDDEN:
                    return True
            except Exception:
                pass
        return False

    elif "darwin" in os_family_lower or "mac" in os_family_lower:
        norm = clean_path.replace("\\", "/").rstrip("/")
        if not norm:
            norm = "/"
        if norm in MACOS_FORBIDDEN:
            return True
        if os.name != "nt":
            try:
                resolved = os.path.realpath(clean_path).rstrip("/")
                if not resolved:
                    resolved = "/"
                if resolved in MACOS_FORBIDDEN:
                    return True
            except Exception:
                pass
        return False

    else:
        # Windows
        norm_input = clean_path.replace("/", "\\")
        for pat in WINDOWS_FORBIDDEN:
            if re.match(pat, norm_input, re.IGNORECASE) or re.match(pat, norm_input.rstrip("\\"), re.IGNORECASE):
                return True

        try:
            resolved = os.path.realpath(clean_path)
            norm_res = resolved.replace("/", "\\")
            for pat in WINDOWS_FORBIDDEN:
                if re.match(pat, norm_res, re.IGNORECASE) or re.match(pat, norm_res.rstrip("\\"), re.IGNORECASE):
                    return True
        except Exception:
            pass

        return False


def validate_path_safety(path: str, os_family: str = "Windows") -> Tuple[bool, str]:
    if is_forbidden(path, os_family):
        return False, FORBIDDEN_REFUSAL_MESSAGE
    return True, ""
