"""ATA-Assault BDM drivers for FreeHDBoot + exFAT on APA-Jail (same ATA bus).

FreeHDBoot loads plain ps2atad for PFS; a formatted exFAT MBR slice can trigger a second
BDM ATA module and freeze boot (CosmicScale / OPL PR #1688 class). ATA-Assault replaces
``__sysconf/FMCB/USBD.IRX`` and ``USBHDFSD.IRX`` with a unified BDM stack.

Analogia FunTuna-Fork (alvesbeto): no cartão, BDM Assault em ``mc:/SYS-CONF/`` carrega
**antes** dos IRX FAT em ``mc:/BOOT/`` (``.agents/specs/USB_IRX_MATRIX.md``). No HDD
APA-Jail, o slot equivalente é ``__sysconf/FMCB/`` — ver ``specs/FHDB_FUNTUNA_PARITY.md``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .fhdb_stage import FhdbPayloadResult, _upload_tree
from .pfs_boot import PfsInitError, find_pfsshell

USBD_IRX_URL = "https://github.com/saildot4k/ATA-Assault/releases/download/latest/usbd.irx"
USBHDFSD_IRX_URL = (
    "https://github.com/saildot4k/ATA-Assault/releases/download/latest/usbhdfsd.irx"
)
CACHE_DIR = Path("/tmp/pfs-batchkit/ata-assault")
SYSCONF_USBD = "FMCB/USBD.IRX"
SYSCONF_USBHDFSD = "FMCB/USBHDFSD.IRX"


class ExfatBootSafetyError(Exception):
    """Refusing exFAT mkfs — would cause PS2 black screen on hybrid APA-Jail boot."""


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def allow_exfat_during_prepare() -> bool:
    """Expert override: mkfs exFAT inside ``prepare-device`` (still requires FHDB + ATA-Assault)."""
    return _env_truthy("PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE")


def force_exfat_before_fhdb() -> bool:
    """Unsafe: skip FHDB requirement (ATA-Assault still required unless also skipped)."""
    return _env_truthy("PFS_BATCHKIT_FORCE_EXFAT_BEFORE_FHDB")


@dataclass(frozen=True)
class AtaAssaultBundle:
    usbd: Path
    usbhdfsd: Path


def _skip_ata_assault() -> bool:
    return os.environ.get("PFS_BATCHKIT_SKIP_ATA_ASSAULT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def resolve_defer_exfat_format(explicit: bool | None = None) -> bool:
    """
    Default **True** — ``prepare-device`` nunca formata exFAT no mesmo passo (evita tela preta).

    Só formata no prepare com ``PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE=1`` + FHDB + ATA-Assault,
    ou depois via ``format-exfat`` / segundo prepare.
    """
    if explicit is not None:
        return explicit
    if _env_truthy("PFS_BATCHKIT_DEFER_EXFAT"):
        return True
    if allow_exfat_during_prepare():
        return False
    return True


def fetch_ata_assault_bundle() -> AtaAssaultBundle:
    env_dir = os.environ.get("PFS_BATCHKIT_ATA_ASSAULT_DIR")
    if env_dir:
        root = Path(env_dir).expanduser()
        usbd = root / "usbd.irx"
        hdfsd = root / "usbhdfsd.irx"
        if usbd.is_file() and hdfsd.is_file():
            return AtaAssaultBundle(usbd=usbd, usbhdfsd=hdfsd)

    repo = Path(__file__).resolve().parents[2] / "tools" / "bundled" / "ata-assault"
    if (repo / "usbd.irx").is_file() and (repo / "usbhdfsd.irx").is_file():
        return AtaAssaultBundle(usbd=repo / "usbd.irx", usbhdfsd=repo / "usbhdfsd.irx")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    usbd = CACHE_DIR / "usbd.irx"
    hdfsd = CACHE_DIR / "usbhdfsd.irx"
    for url, dest in ((USBD_IRX_URL, usbd), (USBHDFSD_IRX_URL, hdfsd)):
        if dest.is_file() and dest.stat().st_size > 1024:
            continue
        tmp = dest.with_suffix(".download")
        try:
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(dest)
        except (OSError, urllib.error.URLError) as exc:
            tmp.unlink(missing_ok=True)
            raise OSError(f"Download ATA-Assault falhou ({url}): {exc}") from exc
    if not usbd.is_file() or not hdfsd.is_file():
        raise OSError("ATA-Assault IRX em falta após download")
    return AtaAssaultBundle(usbd=usbd, usbhdfsd=hdfsd)


def probe_ata_assault_installed(device: Path) -> bool:
    """True if ATA-Assault IRXs are present under ``__sysconf/FMCB/``."""
    shell = find_pfsshell()
    if shell is None:
        return False
    script = "\n".join(
        [
            f"device {device.expanduser()}",
            "mount __sysconf",
            "cd FMCB",
            "ls",
            "exit",
            "",
        ]
    )
    proc = subprocess.run(
        [str(shell)],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "").upper()
    return "USBD.IRX" in out and "USBHDFSD.IRX" in out


def fhdb_exfat_boot_safe(
    *,
    fhdb_installed: bool,
    ata_assault_installed: bool,
    format_exfat: bool,
    defer_exfat: bool,
) -> tuple[bool, str | None]:
    """
    Formatted exFAT on APA-Jail + same ATA as PFS → tela preta no boot unless guarded.

    Applies **before** osdmain.elf exists (1º boot wLaunchELF) and after FHDB.
    """
    if not format_exfat or defer_exfat:
        return True, None
    if force_exfat_before_fhdb():
        if not ata_assault_installed:
            return False, (
                "exFAT bloqueado: PFS_BATCHKIT_FORCE_EXFAT_BEFORE_FHDB exige ATA-Assault "
                "em __sysconf/FMCB/."
            )
        return True, None
    if not ata_assault_installed:
        return False, (
            "exFAT bloqueado: falta ATA-Assault em __sysconf/FMCB/. "
            "Superblock exFAT + boot APA trava no IOP (tela preta)."
        )
    if not fhdb_installed:
        return False, (
            "exFAT bloqueado: osdmain.elf (FHDB) ausente. "
            "Instale FHDB no PS2 (FMCBInstaller) ou HDD-OSD no PC; depois use format-exfat."
        )
    return True, None


def assert_safe_to_format_exfat(target: Path) -> None:
    """Raise ``ExfatBootSafetyError`` if mkfs exFAT on this hybrid target is unsafe."""
    from .fhdb_stage import probe_fhdb_installed

    if _skip_ata_assault() and not force_exfat_before_fhdb():
        raise ExfatBootSafetyError(
            "PFS_BATCHKIT_SKIP_ATA_ASSAULT=1 — recusado formatar exFAT (tela preta no PS2)."
        )
    fhdb_ok = probe_fhdb_installed(target)
    ata_ok = probe_ata_assault_installed(target)
    safe, msg = fhdb_exfat_boot_safe(
        fhdb_installed=fhdb_ok,
        ata_assault_installed=ata_ok,
        format_exfat=True,
        defer_exfat=False,
    )
    if not safe:
        raise ExfatBootSafetyError(
            msg
            or "exFAT bloqueado — veja specs/FHDB_OPL_BOOT.md e recover-first-boot."
        )


def install_ata_assault_sysconf(device: Path) -> FhdbPayloadResult:
    """Upload BDM drivers to ``__sysconf/FMCB/`` (FreeHDBoot external driver slots)."""
    if _skip_ata_assault():
        return FhdbPayloadResult((), ("ATA-Assault: ignorado (PFS_BATCHKIT_SKIP_ATA_ASSAULT).",))

    shell = find_pfsshell()
    if shell is None:
        raise PfsInitError(
            "ATA-Assault: pfsshell em falta — obrigatório antes de exFAT no PS2."
        )

    try:
        bundle = fetch_ata_assault_bundle()
    except OSError as exc:
        raise PfsInitError(f"ATA-Assault: {exc}") from exc

    with tempfile.TemporaryDirectory(prefix="pfs-batchkit-ata-assault-") as td:
        staging = Path(td) / "sysconf"
        fmcb = staging / "FMCB"
        fmcb.mkdir(parents=True)
        shutil.copy2(bundle.usbd, fmcb / "USBD.IRX")
        shutil.copy2(bundle.usbhdfsd, fmcb / "USBHDFSD.IRX")
        installed, err = _upload_tree(device, "__sysconf", staging, shell)
        if err:
            raise PfsInitError(err)

    return FhdbPayloadResult(
        installed,
        (
            "ATA-Assault: USBD.IRX + USBHDFSD.IRX em __sysconf/FMCB/ "
            "(BDM + exFAT no mesmo ATA que PFS — evita freeze FHDB).",
        ),
    )
