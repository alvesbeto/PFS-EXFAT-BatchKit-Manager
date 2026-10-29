"""Host preflight and post-prepare checks for PS2 HDD (FHDB + OPL + exFAT)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .boot_loader import resolve_boot_kelf
from .boot_ready import verify_boot_ready
from .fhdb_bdm import fetch_ata_assault_bundle, probe_ata_assault_installed
from .fhdb_stage import manager_hdd_osd_dirs, probe_fhdb_installed
from .host.detect import host_os
from .opl import verify_opl_tree
from .opl_bootstrap import FMCB_INSTALLER_NAME
from .pfs_boot import find_pfsshell, pfsshell_requirements_hint
from .exfat import format_exfat_requirements_hint


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str
    critical: bool = True


@dataclass
class HostDoctorReport:
    items: list[CheckItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(i.ok or not i.critical for i in self.items)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 2


@dataclass
class DeviceVerifyReport:
    items: list[CheckItem] = field(default_factory=list)
    ps2_steps: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return all(i.ok or not i.critical for i in self.items)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 2


def _resolve_fmcb_hint() -> Path | None:
    from .opl_bootstrap import _resolve_fmcb_installer

    return _resolve_fmcb_installer()


def run_host_doctor(*, for_prepare: bool = False) -> HostDoctorReport:
    """
    Verifica dependências no PC antes de prepare-device.

    ``for_prepare=True``: exige pfsshell (init PFS) e ferramentas exFAT no host Linux.
    """
    items: list[CheckItem] = []

    shell = find_pfsshell()
    items.append(
        CheckItem(
            "pfsshell",
            shell is not None,
            str(shell) if shell else pfsshell_requirements_hint(),
            critical=for_prepare,
        )
    )

    if for_prepare and host_os() == "linux":
        mkfs = shutil.which("mkfs.exfat") or shutil.which("mkfs.exfat-fake")
        items.append(
            CheckItem(
                "mkfs.exfat",
                mkfs is not None,
                mkfs or format_exfat_requirements_hint(),
                critical=False,
            )
        )
        items.append(
            CheckItem(
                "losetup",
                shutil.which("losetup") is not None,
                "losetup (montar região exFAT do disco)",
                critical=False,
            )
        )

    try:
        fetch_ata_assault_bundle()
        items.append(
            CheckItem(
                "ata-assault",
                True,
                "USBD/USBHDFSD IRX disponíveis (download ou PFS_BATCHKIT_ATA_ASSAULT_DIR)",
            )
        )
    except OSError as exc:
        items.append(
            CheckItem(
                "ata-assault",
                False,
                str(exc),
                critical=for_prepare,
            )
        )

    system, _ = manager_hdd_osd_dirs()
    fmcb = _resolve_fmcb_hint()
    if system is not None:
        items.append(
            CheckItem(
                "hdd-osd",
                True,
                f"HDD-OSD __system pronto: {system.parent}",
            )
        )
    else:
        items.append(
            CheckItem(
                "hdd-osd",
                False,
                "Sem HDD-OSD/__system (osdmain.elf) — inject FHDB no PC ou FMCBInstaller no PS2",
                critical=False,
            )
        )

    if fmcb is not None:
        items.append(
            CheckItem(
                "fmcb-installer",
                True,
                str(fmcb),
            )
        )
    else:
        items.append(
            CheckItem(
                "fmcb-installer",
                False,
                f"Sem {FMCB_INSTALLER_NAME} — defina PFS_BATCHKIT_FMCB_INSTALLER",
                critical=False,
            )
        )

    kelf = resolve_boot_kelf(None)
    if kelf is not None and kelf.is_file():
        items.append(CheckItem("boot-kelf", True, str(kelf)))
    else:
        items.append(
            CheckItem(
                "boot-kelf",
                False,
                "wLaunchELF R3Z KELF (PS2KEYS + kelftool) ou PFS_BATCHKIT_BOOT_KELF",
                critical=False,
            )
        )

    ref = Path("/tmp/pfs-batchkit/mbr.img")
    if ref.is_file() or os.environ.get("PFS_BATCHKIT_REFERENCE_MBR"):
        items.append(CheckItem("mbr.img", True, "Referência APA-Jail disponível"))
    else:
        items.append(
            CheckItem(
                "mbr.img",
                False,
                "Será baixado de PFS-BatchKit-Manager no prepare",
                critical=False,
            )
        )

    return HostDoctorReport(items=items)


def verify_exfat_scaffold(root: Path, *, cfg_dev: bool = False) -> list[CheckItem]:
    """Valida árvore OPL + configs na raiz exFAT (mass:)."""
    root = root.expanduser().resolve()
    items: list[CheckItem] = []
    ok, missing = verify_opl_tree(root, cfg_dev=cfg_dev)
    items.append(
        CheckItem(
            "exfat-opl-tree",
            ok,
            "OK" if ok else f"Pastas em falta: {', '.join(missing)}",
        )
    )
    conf = root / "conf_opl.cfg"
    if conf.is_file():
        text = conf.read_text(encoding="utf-8", errors="replace")
        need = ("enable_bdm_hdd=1", "hdd_mode=0", "usb_mode=2")
        bad = [k for k in need if k not in text]
        items.append(
            CheckItem(
                "conf_opl.cfg",
                not bad,
                "OK" if not bad else f"Chaves em falta: {', '.join(bad)}",
            )
        )
    else:
        items.append(
            CheckItem(
                "conf_opl.cfg",
                False,
                "Ausente na raiz exFAT",
            )
        )

    apps = root / "conf_apps.cfg"
    items.append(
        CheckItem(
            "conf_apps.cfg",
            apps.is_file() and apps.stat().st_size > 8,
            "OK" if apps.is_file() else "Ausente (lista Apps OPL)",
            critical=False,
        )
    )

    opl_elf = root / "APPS" / "OPL" / "OPNPS2LD.ELF"
    if not opl_elf.is_file():
        opl_elf = root / "APPS" / "OPL" / "OPL.ELF"
    items.append(
        CheckItem(
            "opl-elf",
            opl_elf.is_file(),
            str(opl_elf) if opl_elf.is_file() else "OPNPS2LD.ELF em APPS/OPL/ (download ou local)",
            critical=False,
        )
    )

    fmcb = root / "APPS" / "FreeMcBoot" / FMCB_INSTALLER_NAME
    items.append(
        CheckItem(
            "fmcb-on-exfat",
            fmcb.is_file(),
            str(fmcb) if fmcb.is_file() else "FMCBInstaller para Install FHDB no PS2 (se sem inject PC)",
            critical=False,
        )
    )

    from .wlaunchelf_config import WLE_APPS_SUBDIR, WLE_R3Z_DS34_FILENAME

    wle_elf = root / "APPS" / WLE_APPS_SUBDIR / WLE_R3Z_DS34_FILENAME
    wle_cnf = root / "APPS" / WLE_APPS_SUBDIR / "LAUNCHELF.CNF"
    wle_ok = wle_elf.is_file() and wle_cnf.is_file()
    items.append(
        CheckItem(
            "wlaunchelf-r3z-exfat",
            wle_ok,
            (
                f"{WLE_R3Z_DS34_FILENAME} + LAUNCHELF.CNF (ata:/ exFAT)"
                if wle_ok
                else f"APPS/{WLE_APPS_SUBDIR}/ — R3Z para BDM exFAT no HDD"
            ),
            critical=False,
        )
    )
    return items


def probe_opl_pfs_on_device(device: Path) -> list[CheckItem]:
    shell = find_pfsshell()
    if shell is None:
        return [
            CheckItem("pfs-opl-config", False, "pfsshell em falta", critical=False),
        ]
    script = "\n".join(
        [
            f"device {device.expanduser()}",
            "mount __system",
            "cd OPL",
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
    out = proc.stdout or ""
    has_hdd = "conf_hdd.cfg" in out
    has_apps = "conf_apps.cfg" in out
    return [
        CheckItem(
            "pfs-conf_hdd.cfg",
            has_hdd,
            "__system/OPL/conf_hdd.cfg",
            critical=False,
        ),
        CheckItem(
            "pfs-conf_apps.cfg",
            has_apps,
            "__system/OPL/conf_apps.cfg (paridade FunTuna Apps)",
            critical=False,
        ),
    ]


def verify_device_for_ps2(
    device: Path,
    *,
    expect_exfat_formatted: bool = False,
    expect_fhdb: bool = False,
    exfat_mount: Path | None = None,
    cfg_dev: bool = False,
) -> DeviceVerifyReport:
    """Checklist pós-prepare no disco bruto (+ montagem exFAT opcional)."""
    device = device.expanduser()
    items: list[CheckItem] = []

    boot = verify_boot_ready(device)
    items.append(
        CheckItem("boot-mbr-apaj-kelf", boot.ok, "; ".join(boot.messages[:3]))
    )

    if expect_fhdb or probe_fhdb_installed(device):
        fhdb = probe_fhdb_installed(device)
        items.append(
            CheckItem(
                "fhdb-osdmain",
                fhdb,
                "__system/osd/osdmain.elf (menu OSD no boot)",
                critical=expect_fhdb,
            )
        )
        ata = probe_ata_assault_installed(device)
        items.append(
            CheckItem(
                "ata-assault-sysconf",
                ata,
                "__sysconf/FMCB/USBD.IRX + USBHDFSD.IRX (exFAT + FHDB)",
                critical=fhdb and expect_exfat_formatted,
            )
        )

    items.extend(probe_opl_pfs_on_device(device))

    if exfat_mount is not None and exfat_mount.is_dir():
        items.extend(verify_exfat_scaffold(exfat_mount, cfg_dev=cfg_dev))

    ps2_steps = _ps2_steps(fhdb_ready=probe_fhdb_installed(device), exfat=expect_exfat_formatted)
    return DeviceVerifyReport(items=items, ps2_steps=ps2_steps)


def _ps2_steps(*, fhdb_ready: bool, exfat: bool) -> tuple[str, ...]:
    if fhdb_ready:
        base = (
            "1. Ligue o PS2 com o HDD — deve entrar no menu OSD (FreeHDBoot).",
            "2. Abra OPL (Apps ou menu) — BDM HDD + mass: já configurados.",
            "3. NÃO use Format/Expand no HDD Manager do wLaunchELF.",
        )
        if exfat:
            return base + ("4. ISO/ZSO em mass:/CD e mass:/DVD.",)
        return base + (
            "4. Se exFAT ainda não formatado: após boot FHDB, rode format-exfat no PC.",
        )
    return (
        "1. Boot inicial: wLaunchELF (normal até instalar FHDB).",
        "2. mass: → APPS/FreeMcBoot → FMCBInstaller.elf → Install FHDB (From HDD).",
        "3. Reinicie — menu OSD FHDB.",
        "4. Depois use OPL com conf_opl.cfg na raiz exFAT (BDM).",
    )


def format_doctor_report(report: HostDoctorReport | DeviceVerifyReport) -> list[str]:
    lines: list[str] = []
    for item in report.items:
        tag = "OK" if item.ok else ("FALHA" if item.critical else "AVISO")
        lines.append(f"[{tag}] {item.name}: {item.detail}")
    if isinstance(report, DeviceVerifyReport) and report.ps2_steps:
        lines.append("--- Passos no PS2 ---")
        lines.extend(report.ps2_steps)
    return lines
