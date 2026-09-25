import os
import shutil
import tempfile
import pytest

from host_agent.trash.linux import LinuxTrash
from host_agent.trash.macos import MacOSTrash
from host_agent.trash.windows import WindowsTrash


def test_linux_trash_size_and_empty():
    temp_dir = tempfile.mkdtemp()
    try:
        files_dir = os.path.join(temp_dir, "files")
        info_dir = os.path.join(temp_dir, "info")
        os.makedirs(files_dir)
        os.makedirs(info_dir)

        # Create known-size files: 1 MB + 500 KB = 1.5 MB
        f1 = os.path.join(files_dir, "test1.dat")
        with open(f1, "wb") as f:
            f.write(b"0" * (1024 * 1024))

        f2 = os.path.join(files_dir, "test2.dat")
        with open(f2, "wb") as f:
            f.write(b"1" * (512 * 1024))

        backend = LinuxTrash(trash_path=temp_dir)
        size_bytes = backend._get_trash_size_bytes()
        assert size_bytes == (1024 * 1024) + (512 * 1024)

        pct = backend.get_usage_pct()
        assert pct >= 0.0

        # Empty trash
        res = backend.empty()
        assert res.success is True
        assert len(os.listdir(files_dir)) == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_macos_trash_size_and_empty():
    temp_dir = tempfile.mkdtemp()
    try:
        # Create known-size file: 2 MB
        f1 = os.path.join(temp_dir, "doc.pdf")
        with open(f1, "wb") as f:
            f.write(b"A" * (2 * 1024 * 1024))

        backend = MacOSTrash(trash_path=temp_dir)
        assert backend._get_trash_size_bytes() == 2 * 1024 * 1024

        res = backend.empty()
        assert res.success is True
        assert len(os.listdir(temp_dir)) == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_windows_trash_override_size_and_empty():
    temp_dir = tempfile.mkdtemp()
    try:
        f1 = os.path.join(temp_dir, "file.tmp")
        with open(f1, "wb") as f:
            f.write(b"W" * 5000)

        backend = WindowsTrash(override_path=temp_dir)
        pct = backend.get_usage_pct()
        assert pct >= 0.0

        res = backend.empty()
        assert res.success is True
        assert len(os.listdir(temp_dir)) == 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
