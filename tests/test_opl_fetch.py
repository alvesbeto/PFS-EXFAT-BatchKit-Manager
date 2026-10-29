"""Tests for OPL latest dev fetch."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pfs_batchkit.opl_fetch import OPL_BOOT_ELF_NAME, fetch_latest_opl_elf


def test_fetch_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "custom.elf"
    src.write_bytes(b"\x7fELF" + b"x" * (128 * 1024))
    dest = tmp_path / "dest" / OPL_BOOT_ELF_NAME
    monkeypatch.setenv("PFS_BATCHKIT_OPL_ELF", str(src))
    path, msgs = fetch_latest_opl_elf(dest)
    assert path == dest
    assert dest.read_bytes() == src.read_bytes()
    assert any("PFS_BATCHKIT_OPL_ELF" in m for m in msgs)


def test_fetch_downloads_and_caches(monkeypatch, tmp_path: Path) -> None:
    import pfs_batchkit.opl_fetch as mod

    payload = b"\x7fELF" + b"opl-dev" * 20000
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(mod, "OPL_CACHE_DIR", cache_dir)

    def fake_urlretrieve(url: str, dest: str) -> None:
        Path(dest).write_bytes(payload)

    monkeypatch.setattr(mod.urllib.request, "urlretrieve", fake_urlretrieve)
    monkeypatch.setattr(mod, "_latest_dev_label", lambda: "latest dev (2026-01-01)")

    dest = tmp_path / "exfat" / "APPS" / "OPL" / OPL_BOOT_ELF_NAME
    path, msgs = fetch_latest_opl_elf(dest)
    assert path == dest
    assert dest.read_bytes() == payload
    assert (cache_dir / OPL_BOOT_ELF_NAME).is_file()
    assert any("Open-PS2-Loader" in m for m in msgs)

    dest2 = tmp_path / "exfat2" / OPL_BOOT_ELF_NAME
    path2, msgs2 = fetch_latest_opl_elf(dest2)
    assert path2 == dest2
    assert any("cache OK" in m for m in msgs2)
