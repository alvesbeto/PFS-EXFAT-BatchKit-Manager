"""Boot KELF: R3Z exFAT default, latest fallback, Manager fallback."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import pfs_batchkit.boot_loader as bl


def test_manager_fallback_creates_cache_dir(monkeypatch, tmp_path: Path) -> None:
    cache = tmp_path / "wLaunchELF-build"
    monkeypatch.setattr(bl, "BUILD_CACHE", cache)
    monkeypatch.setattr(bl, "CANONICAL_R3Z_KELF", cache / "wLaunchELF-r3z-exfat.kelf")
    monkeypatch.setattr(bl, "CANONICAL_LATEST_KELF", cache / "wLaunchELF-latest.kelf")
    monkeypatch.setattr(bl, "manager_root_candidates", lambda: ())
    monkeypatch.setattr(bl, "resolve_ps2keys", lambda: None)
    monkeypatch.setenv("PFS_BATCHKIT_WLAUNCHELF_LATEST", "1")
    monkeypatch.delenv("PFS_BATCHKIT_WLAUNCHELF_EXFAT", raising=False)

    payload = b"kelf" * 20000

    def fake_urlretrieve(url: str, dest: str) -> None:
        Path(dest).write_bytes(payload)

    monkeypatch.setattr(bl.urllib.request, "urlretrieve", fake_urlretrieve)

    out = tmp_path / "boot.kelf"
    lines = bl.ensure_boot_kelf(out)
    assert out.read_bytes() == payload
    assert (cache / "manager-boot.kelf").is_file()
    assert any("fallback" in line.lower() or "manager" in line.lower() for line in lines)


def test_exfat_disabled_uses_manager(monkeypatch, tmp_path: Path) -> None:
    cache = tmp_path / "wLaunchELF-build"
    monkeypatch.setattr(bl, "BUILD_CACHE", cache)
    monkeypatch.setenv("PFS_BATCHKIT_WLAUNCHELF_EXFAT", "0")
    monkeypatch.delenv("PFS_BATCHKIT_WLAUNCHELF_LATEST", raising=False)
    manager_kelf = tmp_path / "mgr" / "BAT" / "boot.kelf"
    manager_kelf.parent.mkdir(parents=True)
    manager_kelf.write_bytes(b"mgr" * 25000)

    def roots():
        return (tmp_path / "mgr",)

    monkeypatch.setattr(bl, "manager_root_candidates", roots)
    out = tmp_path / "out.kelf"
    lines = bl.ensure_boot_kelf(out)
    assert out.read_bytes() == manager_kelf.read_bytes()
    assert any("manager" in line.lower() for line in lines)


def test_exfat_default_builds_r3z_kelf(monkeypatch, tmp_path: Path) -> None:
    cache = tmp_path / "wLaunchELF-build"
    monkeypatch.setattr(bl, "BUILD_CACHE", cache)
    canonical = cache / "wLaunchELF-r3z-exfat.kelf"
    monkeypatch.setattr(bl, "CANONICAL_R3Z_KELF", canonical)
    monkeypatch.delenv("PFS_BATCHKIT_WLAUNCHELF_LATEST", raising=False)
    monkeypatch.delenv("PFS_BATCHKIT_BOOT_KELF", raising=False)

    r3z_elf = cache / bl.WLE_R3Z_DS34_FILENAME
    r3z_elf.parent.mkdir(parents=True, exist_ok=True)
    r3z_elf.write_bytes(b"elf" * 30000)

    keys = tmp_path / "PS2KEYS.dat"
    keys.write_bytes(b"keys")

    monkeypatch.setattr(bl, "fetch_wlaunchelf_r3z_elf", lambda: r3z_elf)
    monkeypatch.setattr(bl, "resolve_ps2keys", lambda: keys)
    monkeypatch.setattr(bl, "_find_kelftool", lambda: tmp_path / "kelftool")

    def fake_run(cmd, **kwargs):
        work = Path(kwargs["cwd"])
        (work / "boot.kelf").write_bytes(b"r3z-kelf" * 9000)
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bl.subprocess, "run", fake_run)

    out = tmp_path / "boot.kelf"
    lines = bl.ensure_boot_kelf(out)
    assert out.read_bytes() == canonical.read_bytes()
    assert any("R3Z" in line for line in lines)


def test_stage_wlaunchelf_on_exfat(monkeypatch, tmp_path: Path) -> None:
    elf = tmp_path / bl.WLE_R3Z_DS34_FILENAME
    elf.write_bytes(b"elf" * 40000)
    monkeypatch.setattr(bl, "fetch_wlaunchelf_r3z_elf", lambda: elf)
    root = tmp_path / "exfat"
    root.mkdir()
    msgs = bl.stage_wlaunchelf_on_exfat(root)
    dest = root / "APPS" / bl.WLE_APPS_SUBDIR / bl.WLE_R3Z_DS34_FILENAME
    assert dest.is_file()
    assert (root / "APPS" / bl.WLE_APPS_SUBDIR / "LAUNCHELF.CNF").is_file()
    assert any("LAUNCHELF.CNF" in m for m in msgs)
