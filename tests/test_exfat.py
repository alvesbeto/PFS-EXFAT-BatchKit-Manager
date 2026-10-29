"""exFAT region offset/size helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pfs_batchkit.exfat import exfat_region_bytes
from pfs_batchkit.layout import plan_layout


def test_exfat_offset_1gib():
    layout = plan_layout(1024**3)
    off, size = exfat_region_bytes(layout)
    assert off == layout.exfat_start_sector * 512
    assert size == layout.exfat_sector_count * 512
    assert off == 384 * 1024 * 1024
    assert off + size == layout.total_bytes


if __name__ == "__main__":
    test_exfat_offset_1gib()
    print("ok")
