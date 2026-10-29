"""Tests for OPL runtime bootstrap on exFAT."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.opl_bootstrap import bootstrap_opl_runtime


def test_bootstrap_writes_conf_and_apps(monkeypatch) -> None:
    monkeypatch.setattr(
        "pfs_batchkit.opl_bootstrap.stage_wlaunchelf_on_exfat",
        lambda root: ("wLaunchELF: mock",),
    )
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "exfat"
        root.mkdir()
        result = bootstrap_opl_runtime(root, download_opl=False, copy_fmcb_installer=False)
        assert (root / "conf_opl.cfg").is_file()
        text = (root / "conf_opl.cfg").read_text()
        assert "enable_bdm_hdd=1" in text
        assert "enable_delete_rename=1" in text
        assert "hdd_mode=0" in text
        assert (root / "conf_apps.cfg").is_file()
        assert (result.opl_app_dir / "title.cfg").is_file()
        assert (result.fhdb_app_dir / "title.cfg").is_file()
        assert (result.fhdb_app_dir / "LEIA-ME_FHDB.txt").is_file()
