"""Tests for OPL game copy helper."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.gui.opl_transfer import copy_games_to_opl_library, pick_medium
from pfs_batchkit.opl import write_opl_tree


def test_pick_medium() -> None:
    assert pick_medium(800_000_000) == "DVD"
    assert pick_medium(100_000_000) == "CD"


def test_copy_games() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "opl"
        write_opl_tree(root)
        src = Path(td) / "src"
        src.mkdir()
        iso = src / "SLUS_123.45.iso"
        iso.write_bytes(b"x" * 1000)
        code, lines = copy_games_to_opl_library(root, src)
        assert code == 0
        assert (root / "CD" / "SLUS_123.45.iso").is_file()
        assert any("Copiado" in ln for ln in lines)
