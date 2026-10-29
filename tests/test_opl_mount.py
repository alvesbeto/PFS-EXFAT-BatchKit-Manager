"""Tests for OPL mount path discovery."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.disks import PhysicalDisk
from pfs_batchkit.opl import write_opl_tree
from pfs_batchkit.opl_mount import (
    discover_exfat_volume_root,
    discover_opl_root,
    resolve_scaffold_mount,
    suggest_opl_root_path,
)


def test_discover_opl_root_finds_tree() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "PS2OPL"
        write_opl_tree(root)
        found = discover_opl_root(extra_paths=(root,))
        assert found == root.resolve()


def test_discover_from_disk_mountpoint() -> None:
    with tempfile.TemporaryDirectory() as td:
        mount = Path(td) / "mnt"
        write_opl_tree(mount)
        disk = PhysicalDisk(
            index=1,
            path=Path("/dev/sdb"),
            model="Test",
            size_bytes=1000,
            bus="usb",
            ps2_hdd=False,
            hdl_path="",
            mountpoints=(str(mount),),
            notes="",
        )
        assert discover_opl_root(disk=disk) == mount.resolve()


def test_suggest_uses_discovered_when_mounted() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "vol"
        write_opl_tree(root)
        assert discover_opl_root(extra_paths=(root,)) == root.resolve()
        assert suggest_opl_root_path(disk=None).name == "PS2OPL"


def test_discover_exfat_volume_without_opl_tree() -> None:
    with tempfile.TemporaryDirectory() as td:
        mount = Path(td) / "empty_vol"
        mount.mkdir()
        assert discover_exfat_volume_root(extra_paths=(mount,)) == mount.resolve()


def test_resolve_scaffold_mount_falls_back_to_disk_mountpoint() -> None:
    with tempfile.TemporaryDirectory() as td:
        mount = Path(td) / "mnt"
        mount.mkdir()
        disk = PhysicalDisk(
            index=1,
            path=Path("/dev/sdb"),
            model="Test",
            size_bytes=1000,
            bus="usb",
            ps2_hdd=False,
            hdl_path="",
            mountpoints=(str(mount),),
            notes="",
        )
        resolved, notes = resolve_scaffold_mount(Path("/mnt/ps2hdd"), disk=disk)
        assert resolved == mount.resolve()
        assert notes


def test_parse_opl_mount_message() -> None:
    from pfs_batchkit.opl_mount import opl_mount_message, parse_opl_mount_message

    p = Path("/mnt/PS2OPL")
    assert parse_opl_mount_message(opl_mount_message(p)) == p
    assert parse_opl_mount_message("other") is None
