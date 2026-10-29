"""Tests for OPL folder scaffold (OPL Manager + OPL BDM layout)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.opl import (
    OPL_MANAGER_REQUIRED,
    OPL_DIR_NAMES,
    verify_opl_tree,
    write_opl_tree,
)


def test_write_opl_tree_creates_manager_minimum() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "exfat_root"
        result = write_opl_tree(root, download_opl_elf=False)
        assert result.root == root.resolve()
        for name in OPL_DIR_NAMES:
            assert (root / name).is_dir()
        assert (root / "CFG").is_dir()
        for req in OPL_MANAGER_REQUIRED:
            assert (root / req).is_dir()
        ok, missing = verify_opl_tree(root)
        assert ok, missing
        assert result.readme_path is not None
        assert result.readme_path.is_file()


def test_write_opl_tree_cfg_dev() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "r"
        write_opl_tree(root, cfg_dev=True, download_opl_elf=False)
        assert (root / "CFG-DEV").is_dir()
        assert not (root / "CFG").exists()
