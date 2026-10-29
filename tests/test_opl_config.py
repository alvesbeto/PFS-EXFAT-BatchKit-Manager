"""Tests for OPL config templates."""

from __future__ import annotations

from pfs_batchkit.opl_config import (
    render_conf_apps_opl,
    render_conf_hdd_pfs,
    render_conf_opl_exfat,
)


def test_conf_opl_uses_official_keys() -> None:
    text = render_conf_opl_exfat()
    assert "enable_bdm_hdd=1" in text
    assert "enable_delete_rename=1" in text
    assert "hdd_mode=0" in text
    assert "usb_mode=2" in text
    assert "enable_mx4sio=1" in text
    assert "app_mode=1" in text


def test_conf_apps_fhdb_hybrid() -> None:
    from pfs_batchkit.opl_config import render_conf_apps_fhdb_hybrid

    both = render_conf_apps_fhdb_hybrid()
    assert "Open PS2 Loader=mass:APPS/OPL/OPNPS2LD.ELF" in both
    assert "wLaunchELF R3Z=mass:APPS/wLaunchELF/WLE-R3Z-DS34.ELF" in both
    assert "FreeMcBoot Installer=mass:APPS/FreeMcBoot/FMCBInstaller.elf" in both
    only_opl = render_conf_apps_fhdb_hybrid(include_fmcb_installer=False)
    assert "FreeMcBoot" not in only_opl


def test_conf_hdd_batchkit_common() -> None:
    assert "hdd_partition=__common" in render_conf_hdd_pfs()


def test_conf_apps_mass_path() -> None:
    assert render_conf_apps_opl() == "Open PS2 Loader=mass:APPS/OPL/OPNPS2LD.ELF\r\n"
