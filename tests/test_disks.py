"""Tests for physical disk listing and BatchKit-style selection."""

from __future__ import annotations

from pathlib import Path

from pfs_batchkit.disks import (
    PhysicalDisk,
    format_disk_listing,
    resolve_disk_selection,
)


def _sample_disks() -> list[PhysicalDisk]:
    return [
        PhysicalDisk(
            index=0,
            path=Path("/dev/sda"),
            model="System SSD",
            size_bytes=500 * 1024**3,
            bus="sata",
            ps2_hdd=False,
            hdl_path="",
            mountpoints=("/",),
            notes="WARNING: system disk",
        ),
        PhysicalDisk(
            index=1,
            path=Path("/dev/sdb"),
            model="PS2 HDD",
            size_bytes=500 * 1024**3,
            bus="usb",
            ps2_hdd=True,
            hdl_path="hdd1:",
            mountpoints=(),
            notes="",
        ),
    ]


def test_resolve_by_index() -> None:
    disks = _sample_disks()
    picked = resolve_disk_selection("1", disks)
    assert picked is not None
    assert picked.path == Path("/dev/sdb")


def test_resolve_by_path() -> None:
    disks = _sample_disks()
    picked = resolve_disk_selection("/dev/sdb", disks)
    assert picked is not None
    assert picked.index == 1


def test_resolve_invalid() -> None:
    assert resolve_disk_selection("99", _sample_disks()) is None


def test_format_listing_includes_index() -> None:
    lines = format_disk_listing(_sample_disks())
    text = "\n".join(lines)
    assert "[0]" in text and "[1]" in text
    assert "hdl_dump" in text.lower() or "BatchKit" in text
