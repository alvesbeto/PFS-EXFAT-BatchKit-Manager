"""Shared exFAT types (no OS imports)."""

from __future__ import annotations

from dataclasses import dataclass

from .layout import HybridLayout

DEFAULT_VOLUME_LABEL = "PS2OPL"


@dataclass(frozen=True)
class ExfatFormatResult:
    loop_device: str
    mount_point: str
    volume_label: str
    byte_offset: int
    byte_size: int
    mount_persisted: bool = False


class ExfatFormatError(RuntimeError):
    pass


def exfat_region_bytes(layout: HybridLayout) -> tuple[int, int]:
    offset = layout.exfat_start_sector * 512
    size = layout.exfat_sector_count * 512
    return offset, size
