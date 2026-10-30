"""FHDB / HDD-OSD staging helpers."""

from __future__ import annotations

from pathlib import Path

from pfs_batchkit.fhdb_stage import _hdd_osd_system_ready, patch_freehdb_cnf_for_browser


def test_hdd_osd_system_ready_markers(tmp_path: Path) -> None:
    system = tmp_path / "__system"
    assert not _hdd_osd_system_ready(system)
    (system / "osd").mkdir(parents=True)
    (system / "osd" / "osdmain.elf").write_bytes(b"elf")
    assert _hdd_osd_system_ready(system)


def test_freehdb_cnf_browser_patch() -> None:
    sample = (
        "OSDSYS_left_cursor=009\n"
        "OSDSYS_right_cursor=008\n"
        "OSDSYS_menu_bottom_delimiter=006\n"
        "OSDSYS_menu_bottom_delimiter=007\n"
    )
    out = patch_freehdb_cnf_for_browser(sample)
    assert "OSDSYS_left_cursor=006" in out
    assert "OSDSYS_right_cursor=005" in out
    assert "OSDSYS_menu_bottom_delimiter=009" in out
    assert "OSDSYS_menu_bottom_delimiter=010" in out
