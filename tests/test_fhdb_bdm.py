"""FHDB + exFAT boot deferral and ATA-Assault helpers."""

from __future__ import annotations

import os

from pfs_batchkit.fhdb_bdm import resolve_defer_exfat_format


def test_defer_exfat_default() -> None:
    os.environ.pop("PFS_BATCHKIT_DEFER_EXFAT", None)
    os.environ.pop("PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE", None)
    assert resolve_defer_exfat_format(None) is True
    assert resolve_defer_exfat_format(True) is True
    assert resolve_defer_exfat_format(False) is False


def test_defer_exfat_env(monkeypatch) -> None:
    monkeypatch.setenv("PFS_BATCHKIT_DEFER_EXFAT", "1")
    assert resolve_defer_exfat_format(None) is True


def test_format_on_prepare_env(monkeypatch) -> None:
    monkeypatch.delenv("PFS_BATCHKIT_DEFER_EXFAT", raising=False)
    monkeypatch.setenv("PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE", "1")
    assert resolve_defer_exfat_format(None) is False


def test_fhdb_exfat_boot_safe_requires_ata_assault() -> None:
    from pfs_batchkit.fhdb_bdm import fhdb_exfat_boot_safe

    ok, msg = fhdb_exfat_boot_safe(
        fhdb_installed=True,
        ata_assault_installed=False,
        format_exfat=True,
        defer_exfat=False,
    )
    assert ok is False
    assert msg and "bloqueado" in msg
    ok2, _ = fhdb_exfat_boot_safe(
        fhdb_installed=True,
        ata_assault_installed=True,
        format_exfat=True,
        defer_exfat=False,
    )
    assert ok2 is True


def test_fhdb_exfat_boot_safe_defers_without_fhdb() -> None:
    from pfs_batchkit.fhdb_bdm import fhdb_exfat_boot_safe

    ok, msg = fhdb_exfat_boot_safe(
        fhdb_installed=False,
        ata_assault_installed=True,
        format_exfat=True,
        defer_exfat=False,
    )
    assert ok is False
    assert msg and "bloqueado" in msg
