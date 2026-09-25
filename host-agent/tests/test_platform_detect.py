import os
from unittest.mock import patch, mock_open
import pytest

from host_agent.platform_detect import detect


def test_detect_windows():
    with patch("platform.system", return_value="Windows"), \
         patch("platform.release", return_value="11"), \
         patch("platform.version", return_value="10.0.22631"):
        info = detect()
        assert info["os_family"] == "Windows"
        assert info["distro_id"] == "windows"
        assert "Windows 11" in info["distro_name"]
        assert info["trash_path"] == "shell:RecycleBinFolder"


def test_detect_macos():
    with patch("platform.system", return_value="Darwin"), \
         patch("platform.mac_ver", return_value=("14.2.1", ("", "", ""), "")):
        info = detect()
        assert info["os_family"] == "Darwin"
        assert info["distro_id"] == "macos"
        assert info["init_system"] == "launchd"
        assert info["trash_path"].endswith(".Trash")


def test_detect_linux_ubuntu():
    os_release_content = """NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
VERSION_ID="22.04"
"""
    with patch("platform.system", return_value="Linux"), \
         patch("builtins.open", mock_open(read_data=os_release_content)), \
         patch("shutil.which", side_effect=lambda x: "/usr/bin/apt-get" if x == "apt-get" else None):
        info = detect()
        assert info["os_family"] == "Linux"
        assert info["distro_id"] == "ubuntu"
        assert info["package_manager"] == "apt"
        assert info["trash_path"].endswith(".local/share/Trash")


def test_detect_linux_fedora():
    os_release_content = """NAME="Fedora Linux"
VERSION="39 (Workstation Edition)"
ID=fedora
VERSION_ID="39"
"""
    with patch("platform.system", return_value="Linux"), \
         patch("builtins.open", mock_open(read_data=os_release_content)), \
         patch("shutil.which", side_effect=lambda x: "/usr/bin/dnf" if x == "dnf" else None):
        info = detect()
        assert info["os_family"] == "Linux"
        assert info["distro_id"] == "fedora"
        assert info["package_manager"] == "dnf"


def test_detect_linux_alpine():
    os_release_content = """NAME="Alpine Linux"
ID=alpine
VERSION_ID="3.19.1"
"""
    with patch("platform.system", return_value="Linux"), \
         patch("builtins.open", mock_open(read_data=os_release_content)), \
         patch("shutil.which", side_effect=lambda x: "/sbin/apk" if x == "apk" else None):
        info = detect()
        assert info["os_family"] == "Linux"
        assert info["distro_id"] == "alpine"
        assert info["package_manager"] == "apk"
