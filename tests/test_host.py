"""Host platform dispatch tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pfs_batchkit.host.detect import host_os
from pfs_batchkit.host.exfat import format_exfat_requirements_hint


def test_host_os_value():
    assert host_os() in ("linux", "darwin", "windows")


def test_requirements_hint_non_empty():
    hint = format_exfat_requirements_hint()
    assert hint


if __name__ == "__main__":
    test_host_os_value()
    test_requirements_hint_non_empty()
    print("ok")
