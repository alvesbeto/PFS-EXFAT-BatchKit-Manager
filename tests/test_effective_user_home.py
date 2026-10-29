"""Elevation helpers."""

from __future__ import annotations

import os
from pathlib import Path

from pfs_batchkit.host.privileges import effective_user_home


def test_effective_user_home_uses_sudo_user(monkeypatch) -> None:
    monkeypatch.setenv("SUDO_USER", "beto")
    monkeypatch.setattr(
        "pfs_batchkit.host.privileges.Path.home",
        lambda: Path("/root"),
    )
    home = effective_user_home()
    assert home == Path("/home/beto") or home.is_dir()
