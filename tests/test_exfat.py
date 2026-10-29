"""exFAT region offset/size helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pfs_batchkit.exfat import exfat_region_bytes
from pfs_batchkit.layout import plan_layout, plan_layout_placeholder


def test_exfat_offset_1gib():
    layout = plan_layout(1024**3)
    off, size = exfat_region_bytes(layout)
    assert off == layout.exfat_start_sector * 512
    assert size == layout.exfat_sector_count * 512
    assert off == 384 * 1024 * 1024
    assert off + size == layout.total_bytes


def test_plan_layout_placeholder_valid() -> None:
    layout = plan_layout_placeholder()
    assert layout.exfat_sector_count >= 2048


def test_plan_layout_rejects_boot_only_size() -> None:
    import pytest

    with pytest.raises(ValueError, match="exFAT"):
        plan_layout(384 * 1024**2)


if __name__ == "__main__":
    test_exfat_offset_1gib()
    print("ok")
