"""FHDB / HDD-OSD staging helpers."""

from __future__ import annotations

from pathlib import Path

from pfs_batchkit.fhdb_stage import _hdd_osd_system_ready


def test_hdd_osd_system_ready_markers(tmp_path: Path) -> None:
    system = tmp_path / "__system"
    assert not _hdd_osd_system_ready(system)
    (system / "osd").mkdir(parents=True)
    (system / "osd" / "osdmain.elf").write_bytes(b"elf")
    assert _hdd_osd_system_ready(system)
