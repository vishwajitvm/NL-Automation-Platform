import pytest
from host_agent.safety.denylist import is_forbidden, validate_path_safety, FORBIDDEN_REFUSAL_MESSAGE


def test_host_agent_windows_forbidden_paths():
    assert is_forbidden("C:\\", "Windows") is True
    assert is_forbidden("c:", "Windows") is True
    assert is_forbidden("D:\\", "Windows") is True
    assert is_forbidden("C:\\Windows", "Windows") is True
    assert is_forbidden("C:\\Program Files", "Windows") is True
    assert is_forbidden("C:\\Users", "Windows") is True


def test_host_agent_windows_allowed_paths():
    assert is_forbidden("C:\\Users\\vishw\\Downloads", "Windows") is False
    assert is_forbidden("C:\\temp\\cache", "Windows") is False


def test_host_agent_linux_forbidden_paths():
    assert is_forbidden("/", "Linux") is True
    assert is_forbidden("/etc", "Linux") is True
    assert is_forbidden("/home", "Linux") is True


def test_host_agent_linux_allowed_paths():
    assert is_forbidden("/home/user/cache", "Linux") is False


def test_host_agent_refusal_message():
    safe, msg = validate_path_safety("C:\\Windows", "Windows")
    assert safe is False
    assert msg == FORBIDDEN_REFUSAL_MESSAGE
