"""Windows exFAT backend (diskpart on VHD-backed image file)."""

from __future__ import annotations

import os
import string
import textwrap
from pathlib import Path

from ..exfat_types import (
    DEFAULT_VOLUME_LABEL,
    ExfatFormatError,
    ExfatFormatResult,
    exfat_region_bytes,
)
from ..layout import HybridLayout
from ..opl import write_opl_tree
from .runner import PrivilegeError, is_admin, run_cmd


def requirements_hint() -> str:
    if not is_admin():
        return "Run in an Administrator terminal (diskpart + format exFAT)"
    return "OK (Windows Admin + diskpart exFAT)"


def _free_drive_letter() -> str:
    used = set()
    for letter in string.ascii_uppercase[2:]:  # skip A,B
        if Path(f"{letter}:/").exists():
            used.add(letter)
    for letter in string.ascii_uppercase[2:]:
        if letter not in used:
            return f"{letter}:"
    raise ExfatFormatError("no free drive letter for OPL scaffold")


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
    del use_sudo, mount_parent, keep_mounted_at  # Windows uses Administrator, not sudo

    if not is_admin():
        raise ExfatFormatError(requirements_hint())

    offset, size = exfat_region_bytes(layout)
    if size < 1024 * 1024:
        raise ExfatFormatError("exFAT region smaller than 1 MiB")

    label = volume_label[:15]
    offset_kb = offset // 1024
    size_mb = max(1, size // (1024 * 1024))
    win_path = str(image_path.resolve())

    letter = _free_drive_letter() if scaffold_opl else ""
    lines = [
        f'select vdisk file="{win_path}"',
        "attach vdisk readonly=no",
        f"create partition primary offset={offset_kb} size={size_mb}",
        f'format fs=exfat label="{label}" quick',
    ]
    if scaffold_opl:
        lines.append(f"assign letter={letter[0]}")
    lines.append("exit")

    script = "\n".join(lines)
    mount_point_str = ""

    try:
        run_cmd(["diskpart"], input_text=script, use_sudo=False)

        if scaffold_opl:
            mount_path = Path(f"{letter}\\")
            write_opl_tree(mount_path, cfg_dev=cfg_dev, volume_label=label)
            mount_point_str = str(mount_path)
            cleanup = textwrap.dedent(
                f"""\
                select volume {letter[0]}
                remove letter={letter[0]}
                select vdisk file="{win_path}"
                detach vdisk
                exit
                """
            )
            run_cmd(["diskpart"], input_text=cleanup, use_sudo=False)
        else:
            cleanup = textwrap.dedent(
                f"""\
                select vdisk file="{win_path}"
                detach vdisk
                exit
                """
            )
            run_cmd(["diskpart"], input_text=cleanup, use_sudo=False)

        return ExfatFormatResult(
            loop_device=f'vdisk:"{win_path}"',
            mount_point=mount_point_str,
            volume_label=label,
            byte_offset=offset,
            byte_size=size,
        )
    except PrivilegeError as exc:
        raise ExfatFormatError(str(exc)) from exc
