import pytest
from app.safety.denylist import is_forbidden, validate_path_safety, FORBIDDEN_REFUSAL_MESSAGE


def test_windows_forbidden_paths():
    assert is_forbidden("C:\\", "Windows") is True
    assert is_forbidden("c:", "Windows") is True
    assert is_forbidden("D:\\", "Windows") is True
    assert is_forbidden("C:\\Windows", "Windows") is True
    assert is_forbidden("C:\\Windows\\System32", "Windows") is True
    assert is_forbidden("C:\\Program Files", "Windows") is True
    assert is_forbidden("C:\\Program Files (x86)", "Windows") is True
    assert is_forbidden("C:\\ProgramData", "Windows") is True
    assert is_forbidden("C:\\Users", "Windows") is True


def test_windows_allowed_paths():
    assert is_forbidden("C:\\Users\\vishw\\Downloads", "Windows") is False
    assert is_forbidden("C:\\temp\\cache", "Windows") is False
    assert is_forbidden("D:\\projects\\build", "Windows") is False


def test_linux_forbidden_paths():
    assert is_forbidden("/", "Linux") is True
    assert is_forbidden("/etc", "Linux") is True
    assert is_forbidden("/usr", "Linux") is True
    assert is_forbidden("/boot", "Linux") is True
    assert is_forbidden("/root", "Linux") is True
    assert is_forbidden("/home", "Linux") is True


def test_linux_allowed_paths():
    assert is_forbidden("/home/user/cache", "Linux") is False
    assert is_forbidden("/tmp/myfolder", "Linux") is False


def test_macos_forbidden_paths():
    assert is_forbidden("/", "Darwin") is True
    assert is_forbidden("/System", "Darwin") is True
    assert is_forbidden("/Library", "Darwin") is True
    assert is_forbidden("/Users", "Darwin") is True


def test_macos_allowed_paths():
    assert is_forbidden("/Users/john/Downloads", "Darwin") is False


def test_refusal_message():
    safe, msg = validate_path_safety("C:\\Windows", "Windows")
    assert safe is False
    assert msg == FORBIDDEN_REFUSAL_MESSAGE

    safe, msg = validate_path_safety("C:\\temp\\mydata", "Windows")
    assert safe is True
    assert msg == ""
