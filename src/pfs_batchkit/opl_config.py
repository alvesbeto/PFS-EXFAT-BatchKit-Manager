"""Open PS2 Loader configuration text (keys from include/config.h)."""

from __future__ import annotations

# https://github.com/ps2homebrew/Open-PS2-Loader — Expansion port HDD MBR+exFAT, BDM mass:
# enable_bdm_hdd, conf_opl.cfg on exFAT root; classic PFS HDLoader off (hdd_mode=0).
# OPL seed alinhado a alvesbeto/Funtuna-Fork (.agents/specs/OPL_INTEGRATION.md):
# usb_mode=2 (BDM USB), enable_mx4sio=1, app_mode=1 (lista Apps).

CONF_OPL_EXFAT_LINES: tuple[str, ...] = (
    "# PFS BatchKit — biblioteca ISO/ZSO na raiz exFAT (mass:/CD, mass:/DVD, …)",
    "# Ref: https://github.com/ps2homebrew/Open-PS2-Loader",
    "# Paridade FunTuna-Fork (alvesbeto): BDM USB + MX4SIO; hdd_mode=0 (sem +OPL PFS).",
    "enable_bdm_hdd=1",
    "enable_delete_rename=1",
    "usb_mode=2",
    "hdd_mode=0",
    "eth_mode=0",
    "app_mode=1",
    "enable_ilink=0",
    "enable_mx4sio=1",
    "enable_sfx=1",
    "enable_boot_snd=1",
    "sfx_volume=90",
    "boot_snd_volume=80",
    "theme=Classic",
    "language_text=English",
    "enable_coverart=1",
    "autorefresh=1",
    "autosort=1",
    "wide_screen=0",
)

# PFS __common/OPL/conf_hdd.cfg (PFS-BatchKit-Manager HDD-OSD template)
CONF_HDD_PFS_LINES: tuple[str, ...] = (
    "# Evita particao +OPL automatica; recursos OSD em __common (BatchKit Manager).",
    "# Jogos ISO: sempre exFAT BDM — conf_opl.cfg na raiz exFAT (mass:).",
    "hdd_partition=__common",
)

CONF_HDD_PFS_EXFAT_NOTE_LINES: tuple[str, ...] = (
    "PFS BatchKit — OPL aponta biblioteca de jogos para o exFAT (BDM HDD interno).",
    "Pastas: mass:/CD mass:/DVD mass:/VMC mass:/CFG mass:/ART …",
    "Config principal: mass:/conf_opl.cfg (enable_bdm_hdd=1, hdd_mode=0).",
    "Nao use modo HDLoader PFS (+OPL) neste disco hibrido APA-Jail.",
)


def render_conf_opl_exfat() -> str:
    return "\r\n".join(CONF_OPL_EXFAT_LINES) + "\r\n"


def render_conf_hdd_pfs() -> str:
    return "\r\n".join(CONF_HDD_PFS_LINES) + "\r\n"


def render_conf_apps_opl(boot_elf: str = "OPNPS2LD.ELF") -> str:
    return f"Open PS2 Loader=mass:APPS/OPL/{boot_elf}\r\n"


def render_conf_apps_fhdb_hybrid(
    boot_elf: str = "OPNPS2LD.ELF",
    *,
    include_fmcb_installer: bool = True,
    fmcb_name: str = "FMCBInstaller.elf",
    include_wlaunchelf_r3z: bool = True,
) -> str:
    """Apps OPL no exFAT (mass:) — paridade lista Apps FunTuna-Fork para FHDB."""
    from .wlaunchelf_config import WLE_APPS_SUBDIR, WLE_R3Z_DS34_FILENAME

    lines = [f"Open PS2 Loader=mass:APPS/OPL/{boot_elf}"]
    if include_wlaunchelf_r3z:
        lines.append(
            f"wLaunchELF R3Z=mass:APPS/{WLE_APPS_SUBDIR}/{WLE_R3Z_DS34_FILENAME}"
        )
    if include_fmcb_installer:
        lines.append(f"FreeMcBoot Installer=mass:APPS/FreeMcBoot/{fmcb_name}")
    return "\r\n".join(lines) + "\r\n"


def render_conf_hdd_exfat_note() -> str:
    return "\r\n".join(CONF_HDD_PFS_EXFAT_NOTE_LINES) + "\r\n"
