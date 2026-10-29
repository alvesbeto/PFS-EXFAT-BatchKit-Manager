"""macOS exFAT backend (hdiutil slice + diskutil / mkfs.exfat)."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from ..exfat_types import (
    DEFAULT_VOLUME_LABEL,
    ExfatFormatError,
    ExfatFormatResult,
    exfat_region_bytes,
)
from ..layout import HybridLayout
from ..opl import write_opl_tree
from .runner import PrivilegeError, run_cmd

_DISK_DEV = re.compile(r"/dev/disk\d+")


def requirements_hint() -> str:
    missing = []
    if shutil.which("hdiutil") is None:
        missing.append("hdiutil")
    if shutil.which("diskutil") is None:
        missing.append("diskutil")
    has_mkfs = shutil.which("mkfs.exfat") or shutil.which("mkfs.exfat-fuse")
    if has_mkfs is None and shutil.which("diskutil") is None:
        missing.append("diskutil or mkfs.exfat (brew install exfatprogs)")
    if missing:
        return "Missing: " + ", ".join(missing)
    return "OK (macOS + diskutil/hdiutil + admin/sudo)"


def _parse_disk_device(output: str) -> str:
    for line in output.splitlines():
        m = _DISK_DEV.search(line)
        if m:
            return m.group(0)
    raise ExfatFormatError(f"could not parse disk device from hdiutil output:\n{output}")


def format_exfat_region(
    image_path: Path,
    layout: HybridLayout,
    *,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    scaffold_opl: bool = True,
    cfg_dev: bool = False,
    mount_parent: Path | None = None,
    keep_mounted_at: Path | None = None,
    use_sudo: bool | None = None,
) -> ExfatFormatResult:
    del keep_mounted_at
    if use_sudo is None:
        use_sudo = os.environ.get("PFS_BATCHKIT_USE_SUDO", "1") == "1"

    offset, size = exfat_region_bytes(layout)
    if size < 1024 * 1024:
        raise ExfatFormatError("exFAT region smaller than 1 MiB")

    label = volume_label[:15]
    spec = f"sector={layout.exfat_start_sector},length={size}"
    disk_dev: str | None = None
    mount_point: Path | None = None

    try:
        attach = run_cmd(
            [
                "hdiutil",
                "attach",
                "-nomount",
                "-imagekey",
                f"disk-image-specification={spec}",
                str(image_path),
            ],
            use_sudo=use_sudo,
        )
        disk_dev = _parse_disk_device(attach.stdout + attach.stderr)

        mkfs = shutil.which("mkfs.exfat") or shutil.which("mkfs.exfat-fuse")
        if mkfs:
            run_cmd([mkfs, "-n", label, disk_dev], use_sudo=use_sudo)
        else:
            run_cmd(
                ["diskutil", "eraseVolume", "ExFAT", label, disk_dev],
                use_sudo=use_sudo,
            )

        if scaffold_opl:
            mount_point = Path(
                tempfile.mkdtemp(
                    prefix="pfs-batchkit-exfat-",
                    dir=str(mount_parent) if mount_parent else None,
                )
            )
            run_cmd(["mount", "-t", "exfat", disk_dev, str(mount_point)], use_sudo=use_sudo)
            try:
                write_opl_tree(mount_point, cfg_dev=cfg_dev, volume_label=label)
            finally:
                run_cmd(["umount", str(mount_point)], use_sudo=use_sudo)
                mount_point.rmdir()

        return ExfatFormatResult(
            loop_device=disk_dev,
            mount_point=str(mount_point or ""),
            volume_label=label,
            byte_offset=offset,
            byte_size=size,
        )
    except PrivilegeError as exc:
        raise ExfatFormatError(str(exc)) from exc
    finally:
        if disk_dev:
            try:
                run_cmd(["hdiutil", "detach", disk_dev, "-force"], use_sudo=use_sudo)
            except (ExfatFormatError, PrivilegeError):
                pass
