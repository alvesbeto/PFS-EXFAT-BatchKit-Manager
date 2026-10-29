"""Format the exFAT game region inside a hybrid disk image (multi-OS)."""

from __future__ import annotations

from .exfat_types import (
    DEFAULT_VOLUME_LABEL,
    ExfatFormatError,
    ExfatFormatResult,
    exfat_region_bytes,
)
from .host.exfat import format_exfat_region, format_exfat_requirements_hint

__all__ = [
    "DEFAULT_VOLUME_LABEL",
    "ExfatFormatError",
    "ExfatFormatResult",
    "exfat_region_bytes",
    "format_exfat_region",
    "format_exfat_requirements_hint",
]
