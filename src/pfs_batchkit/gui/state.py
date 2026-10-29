"""Shared wizard state between Qt pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from ..disks import PhysicalDisk
from ..host.privileges import effective_user_home
from ..opl_mount import suggest_opl_root_path


def _default_ps2_image() -> Path:
    return effective_user_home() / "ps2-hdd.img"


def _default_isos_dir() -> Path:
    return effective_user_home() / "ISOs"


def _default_scaffold_mount() -> Path:
    return suggest_opl_root_path()


class WizardMode(StrEnum):
    PREPARE_DISK = "prepare"
    PREPARE_PFS = "prepare_pfs"
    VALIDATE_LAYOUT = "validate"
    ADVANCED = "advanced"


class AdvancedAction(StrEnum):
    BUILD_IMAGE = "build"
    VALIDATE = "validate"
    SCAFFOLD_OPL = "scaffold"


@dataclass
class WizardState:
    mode: WizardMode = WizardMode.PREPARE_DISK
    advanced_action: AdvancedAction | None = None

    selected_disk: PhysicalDisk | None = None
    reference_mbr: Path = Path("/tmp/pfs-batchkit/mbr.img")
    init_pfs: bool = True
    format_exfat: bool = False
    scaffold_opl: bool = True
    defer_exfat_format: bool = True
    cfg_dev: bool = False
    sudo_password: str = ""

    image_path: Path = field(default_factory=_default_ps2_image)
    validate_strict: bool = False
    validate_require_exfat: bool = False

    build_size_gib: float = 500.0
    build_output: Path = field(default_factory=_default_ps2_image)
    build_init_pfs: bool = False
    build_format_exfat: bool = False

    opl_root: Path = Path("/mnt/PS2OPL")
    games_source_dir: Path = field(default_factory=_default_isos_dir)
    games_medium: str = "auto"  # auto | CD | DVD

    scaffold_mount: Path = field(default_factory=_default_scaffold_mount)

    log_lines: list[str] = field(default_factory=list)
    exit_code: int = 2
    done_title: str = "Concluído"
