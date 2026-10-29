"""Tests for host/device readiness checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.device_readiness import (
    run_host_doctor,
    verify_exfat_scaffold,
)
from pfs_batchkit.opl import write_opl_tree


def test_host_doctor_runs() -> None:
    report = run_host_doctor(for_prepare=False)
    assert report.items
    names = {i.name for i in report.items}
    assert "pfsshell" in names
    assert "ata-assault" in names


def test_verify_exfat_scaffold_after_bootstrap() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_opl_tree(root, download_opl_elf=False)
        items = verify_exfat_scaffold(root)
        by_name = {i.name: i for i in items}
        assert by_name["conf_opl.cfg"].ok
        assert by_name["exfat-opl-tree"].ok
        assert (root / "LEIA-ME_PS2_BOOT.txt").is_file()
