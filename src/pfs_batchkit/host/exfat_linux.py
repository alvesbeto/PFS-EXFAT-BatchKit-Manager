"""Linux exFAT backend (losetup + mkfs.exfat)."""

from __future__ import annotations

import os
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


def requirements_hint() -> str:
    missing = []
    if shutil.which("losetup") is None:
        missing.append("losetup")
    if shutil.which("mkfs.exfat") is None and shutil.which("mkfs.exfat-fuse") is None:
        missing.append("mkfs.exfat (package exfatprogs)")
    if missing:
        return "Missing: " + ", ".join(missing)
    return "OK (Linux + exfatprogs + root/sudo)"


def _target_owner_ids() -> tuple[int, int]:
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if sudo_uid and sudo_gid:
        return int(sudo_uid), int(sudo_gid)
    return os.getuid(), os.getgid()


def _mount_exfat_loop_at(
    loop_dev: str,
    mount_point: Path,
    *,
    use_sudo: bool,
) -> None:
    if shutil.which("mount") is None:
        raise ExfatFormatError("mount not found")
    mount_point = mount_point.expanduser()
    mount_point.parent.mkdir(parents=True, exist_ok=True)
    if mount_point.is_dir():
        try:
            run_cmd(["umount", str(mount_point)], use_sudo=use_sudo)
        except (ExfatFormatError, PrivilegeError):
            pass
    elif mount_point.exists():
        raise ExfatFormatError(f"cannot mount: {mount_point} exists and is not a directory")
    else:
        mount_point.mkdir(parents=True)
    uid, gid = _target_owner_ids()
    opts = f"uid={uid},gid={gid},fmask=0022,dmask=0022"
    run_cmd(
        ["mount", "-t", "exfat", "-o", opts, loop_dev, str(mount_point)],
        use_sudo=use_sudo,
    )


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
    if use_sudo is None:
        use_sudo = os.environ.get("PFS_BATCHKIT_USE_SUDO", "1") == "1"

    mkfs = shutil.which("mkfs.exfat") or shutil.which("mkfs.exfat-fuse")
    if mkfs is None:
        raise ExfatFormatError(
            "mkfs.exfat not found; install exfatprogs (Debian/Ubuntu: exfatprogs)"
        )

    offset, size = exfat_region_bytes(layout)
    if size < 1024 * 1024:
        raise ExfatFormatError("exFAT region smaller than 1 MiB")

    label = volume_label[:15]
    loop_dev: str | None = None
    mount_point: Path | None = None
    keep_loop_attached = False

    try:
        setup = run_cmd(
            [
                "losetup",
                "-f",
                "--show",
                f"--offset={offset}",
                f"--sizelimit={size}",
                str(image_path),
            ],
            use_sudo=use_sudo,
        )
        loop_dev = setup.stdout.strip()
        if not loop_dev.startswith("/dev/"):
            raise ExfatFormatError(f"unexpected losetup output: {loop_dev!r}")

        run_cmd([mkfs, "-n", label, loop_dev], use_sudo=use_sudo)

        if scaffold_opl:
            if shutil.which("mount") is None:
                raise ExfatFormatError("mount not found; cannot scaffold OPL tree")
            temp_mount = Path(
                tempfile.mkdtemp(
                    prefix="pfs-batchkit-exfat-",
                    dir=str(mount_parent) if mount_parent else None,
                )
            )
            run_cmd(["mount", loop_dev, str(temp_mount)], use_sudo=use_sudo)
            try:
                write_opl_tree(
                    temp_mount,
                    cfg_dev=cfg_dev,
                    volume_label=label,
                )
            finally:
                run_cmd(["umount", str(temp_mount)], use_sudo=use_sudo)
                temp_mount.rmdir()

        if keep_mounted_at is not None:
            _mount_exfat_loop_at(loop_dev, keep_mounted_at, use_sudo=use_sudo)
            mount_point = keep_mounted_at.resolve()
            keep_loop_attached = True

        return ExfatFormatResult(
            loop_device=loop_dev,
            mount_point=str(mount_point or ""),
            volume_label=label,
            byte_offset=offset,
            byte_size=size,
            mount_persisted=keep_loop_attached,
        )
    except PrivilegeError as exc:
        raise ExfatFormatError(str(exc)) from exc
    finally:
        if loop_dev and not keep_loop_attached:
            try:
                run_cmd(["losetup", "-d", loop_dev], use_sudo=use_sudo)
            except (ExfatFormatError, PrivilegeError):
                pass
