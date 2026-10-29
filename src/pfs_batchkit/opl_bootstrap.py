"""OPL + FHDB staging on exFAT (BDM boot), aligned with PFS-BatchKit-Manager USB layout."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .boot_loader import stage_wlaunchelf_on_exfat
from .opl_config import render_conf_apps_fhdb_hybrid, render_conf_opl_exfat
from .opl_fetch import OPL_BOOT_ELF_NAME, fetch_latest_opl_elf

OPL_APPS_DIR = "OPL"
FHDB_APPS_DIR = "FreeMcBoot"
FMCB_INSTALLER_NAME = "FMCBInstaller.elf"


def _preserve_opl_cfg() -> bool:
    return os.environ.get("PFS_BATCHKIT_PRESERVE_OPL_CFG", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


@dataclass(frozen=True)
class OplBootstrapResult:
    conf_opl: Path
    conf_apps: Path
    opl_app_dir: Path
    fhdb_app_dir: Path
    opl_elf: Path | None
    fhdb_installer: Path | None
    messages: tuple[str, ...]


def _write_conf_opl(root: Path) -> Path:
    path = root / "conf_opl.cfg"
    if _preserve_opl_cfg() and path.is_file() and path.stat().st_size > 32:
        return path
    path.write_text(render_conf_opl_exfat(), encoding="utf-8")
    return path


def _write_conf_apps(root: Path, boot_name: str, *, fmcb_on_disk: bool) -> Path:
    path = root / "conf_apps.cfg"
    if _preserve_opl_cfg() and path.is_file() and path.stat().st_size > 8:
        return path
    body = render_conf_apps_fhdb_hybrid(
        boot_name,
        include_fmcb_installer=fmcb_on_disk,
        fmcb_name=FMCB_INSTALLER_NAME,
    )
    path.write_text(body, encoding="utf-8")
    return path


def _write_title_cfg(app_dir: Path, *, title: str, boot: str) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "title.cfg").write_text(
        f"title={title}\nboot={boot}\nversion=1.0\n",
        encoding="utf-8",
    )


def _resolve_fmcb_installer() -> Path | None:
    env = os.environ.get("PFS_BATCHKIT_FMCB_INSTALLER")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    repo_tools = Path(__file__).resolve().parents[2] / "tools" / "bundled" / FMCB_INSTALLER_NAME
    if repo_tools.is_file():
        return repo_tools
    manager_roots = (
        Path.home() / "PFS-BatchKit-Manager",
        Path(__file__).resolve().parents[3] / "PFS-BatchKit-Manager",
    )
    for base in manager_roots:
        for rel in (
            f"PFS-BatchKit-Manager/!COPY_TO_USB_ROOT/APPS/FreeMcBoot/{FMCB_INSTALLER_NAME}",
            f"!COPY_TO_USB_ROOT/APPS/FreeMcBoot/{FMCB_INSTALLER_NAME}",
            f"APPS/FreeMcBoot/{FMCB_INSTALLER_NAME}",
        ):
            candidate = base / rel
            if candidate.is_file():
                return candidate
    return None


def bootstrap_opl_runtime(
    exfat_root: Path,
    *,
    download_opl: bool = True,
    copy_fmcb_installer: bool = True,
) -> OplBootstrapResult:
    """
    After ``write_opl_tree``: OPL exFAT config, APPS, FMCB installer (BatchKit USB layout).

    Jogos e ``conf_opl.cfg`` ficam na raiz exFAT (BDM ``mass:``). Config PFS em ``__system/OPL/``
    e instalada em ``install_opl_pfs_config`` após ``init-pfs``.
    """
    root = exfat_root.expanduser().resolve()
    messages: list[str] = []

    conf = _write_conf_opl(root)
    messages.append("conf_opl.cfg (enable_bdm_hdd, hdd_mode=0, gravação)")

    opl_dir = root / "APPS" / OPL_APPS_DIR
    opl_elf: Path | None = None
    boot_name = OPL_BOOT_ELF_NAME
    if download_opl:
        opl_elf, opl_msgs = fetch_latest_opl_elf(opl_dir / boot_name)
        messages.extend(opl_msgs)
        if opl_elf is None:
            boot_name = "OPL.ELF"
            if (opl_dir / boot_name).is_file():
                opl_elf = opl_dir / boot_name
                messages.append(f"OPL: fallback {boot_name} local em APPS/OPL/")
            else:
                messages.append(
                    "OPL: coloque OPNPS2LD.ELF em APPS/OPL/ ou defina PFS_BATCHKIT_OPL_ELF."
                )
    else:
        for name in (OPL_BOOT_ELF_NAME, "OPL.ELF"):
            if (opl_dir / name).is_file():
                opl_elf = opl_dir / name
                boot_name = name
                break
    _write_title_cfg(opl_dir, title="Open PS2 Loader", boot=boot_name)

    fhdb_dir = root / "APPS" / FHDB_APPS_DIR
    fhdb_installer: Path | None = None
    if copy_fmcb_installer:
        src = _resolve_fmcb_installer()
        if src is not None:
            fhdb_dir.mkdir(parents=True, exist_ok=True)
            dest = fhdb_dir / FMCB_INSTALLER_NAME
            if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dest)
            fhdb_installer = dest
            messages.append(f"FHDB: {FMCB_INSTALLER_NAME} em APPS/FreeMcBoot/")
        else:
            messages.append(
                "FHDB: defina PFS_BATCHKIT_FMCB_INSTALLER ou copie FMCBInstaller.elf "
                "para APPS/FreeMcBoot/ (BatchKit !COPY_TO_USB_ROOT)."
            )
    elif (fhdb_dir / FMCB_INSTALLER_NAME).is_file():
        fhdb_installer = fhdb_dir / FMCB_INSTALLER_NAME

    conf_apps = _write_conf_apps(
        root,
        boot_name,
        fmcb_on_disk=fhdb_installer is not None,
    )
    messages.append("conf_apps.cfg (OPL Apps: mass:APPS/OPL + FreeMcBoot se presente)")

    _write_title_cfg(
        fhdb_dir,
        title="FreeMcBoot Installer",
        boot=FMCB_INSTALLER_NAME,
    )
    fhdb_dir.mkdir(parents=True, exist_ok=True)
    (fhdb_dir / "LEIA-ME_FHDB.txt").write_text(
        _fhdb_readme_text(),
        encoding="utf-8",
    )
    (root / "LEIA-ME_PS2_BOOT.txt").write_text(
        _ps2_device_checklist_text(fhdb_installer is not None),
        encoding="utf-8",
    )

    messages.extend(stage_wlaunchelf_on_exfat(root))

    return OplBootstrapResult(
        conf_opl=conf,
        conf_apps=conf_apps,
        opl_app_dir=opl_dir,
        fhdb_app_dir=fhdb_dir,
        opl_elf=opl_elf,
        fhdb_installer=fhdb_installer,
        messages=tuple(messages),
    )


def _fhdb_readme_text() -> str:
    return """PFS BatchKit — instalar FreeHDBoot (uma vez)

Igual ao PFS-BatchKit-Manager após preparar o disco no PC:

1. Coloque o HDD no PS2 e ligue — abre wLaunchELF (normal na 1ª vez; ainda não é menu OSD FHDB).
2. wLaunchELF → exFAT BDM (mass:) → APPS → FreeMcBoot.
3. Execute FMCBInstaller.elf → R1 → Install FHDB (From HDD) — aguarde sucesso.
4. Reinicie com o HDD. Agora boot FreeHDBoot / menu OSD. NÃO use Format/Expand no HDD Manager do wLaunchELF.

Biblioteca OPL (ISO/ZSO): pastas CD/ e DVD/ na raiz exFAT — conf_opl.cfg já activa BDM HDD.
Config PFS (__system/OPL/conf_hdd.cfg): hdd_partition=__common (BatchKit), jogos no exFAT.
"""


def _ps2_device_checklist_text(fmcb_on_exfat: bool) -> str:
    fmcb = (
        "3. Se ainda não injectou FHDB no PC: APPS/FreeMcBoot/FMCBInstaller.elf → Install FHDB.\n"
        if fmcb_on_exfat
        else "3. Copie FMCBInstaller para APPS/FreeMcBoot/ ou injecte HDD-OSD no PC.\n"
    )
    return f"""PFS BatchKit — checklist no PS2 (FreeHDBoot + OPL exFAT)

No PC este volume já tem:
  • conf_opl.cfg (enable_bdm_hdd=1, hdd_mode=0, usb_mode=2 BDM)
  • conf_apps.cfg (OPL Apps)
  • Pastas CD/, DVD/, APPS/OPL/, …

No PS2:
1. Primeiro boot pode abrir wLaunchELF até existir osdmain.elf em __system (FHDB).
2. Drivers ATA-Assault devem estar em __sysconf/FMCB/ (prepare BatchKit).
{fmcb}4. Reinicie → menu OSD FHDB.
5. OPL: Settings → BDM HDD activo; jogos em mass:/CD e mass:/DVD.
6. NÃO formate o HDD no wLaunchELF (Format/Expand).

Pen USB exFAT: use MBR (não GPT); freeze no boot → ver specs/FHDB_FUNTUNA_PARITY.md.
"""
