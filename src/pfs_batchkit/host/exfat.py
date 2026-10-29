"""Dispatch exFAT formatting to the host OS backend."""

from __future__ import annotations

from pathlib import Path

from ..exfat_types import (
    DEFAULT_VOLUME_LABEL,
    ExfatFormatError,
    ExfatFormatResult,
    exfat_region_bytes,
)
from ..layout import HybridLayout
from ..image_io import is_raw_device
from .detect import host_os


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
    image_path = image_path.resolve()
    if not image_path.exists():
        raise ExfatFormatError(f"image or device not found: {image_path}")
    if not image_path.is_file() and not is_raw_device(image_path):
        raise ExfatFormatError(f"not a hybrid image or raw block device: {image_path}")

    from ..fhdb_bdm import ExfatBootSafetyError, assert_safe_to_format_exfat

    try:
        assert_safe_to_format_exfat(image_path)
    except ExfatBootSafetyError as exc:
        raise ExfatFormatError(str(exc)) from exc

    os_name = host_os()
    if os_name == "linux":
        from .exfat_linux import format_exfat_region as fmt
    elif os_name == "darwin":
        from .exfat_darwin import format_exfat_region as fmt
    else:
        from .exfat_windows import format_exfat_region as fmt

    return fmt(
        image_path,
        layout,
        volume_label=volume_label,
        scaffold_opl=scaffold_opl,
        cfg_dev=cfg_dev,
        mount_parent=mount_parent,
        keep_mounted_at=keep_mounted_at,
        use_sudo=use_sudo,
    )


def format_exfat_requirements_hint() -> str:
    os_name = host_os()
    if os_name == "linux":
        from .exfat_linux import requirements_hint
    elif os_name == "darwin":
        from .exfat_darwin import requirements_hint
    else:
        from .exfat_windows import requirements_hint
    return requirements_hint()


__all__ = [
    "DEFAULT_VOLUME_LABEL",
    "ExfatFormatError",
    "ExfatFormatResult",
    "exfat_region_bytes",
    "format_exfat_region",
    "format_exfat_requirements_hint",
]
