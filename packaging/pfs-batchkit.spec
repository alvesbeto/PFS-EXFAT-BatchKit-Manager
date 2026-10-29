# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for pfs-batchkit CLI."""

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent
src = root / "src"

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pfs_batchkit.apa",
        "pfs_batchkit.layout",
        "pfs_batchkit.exfat",
        "pfs_batchkit.pfs_boot",
        "pfs_batchkit.opl",
        "pfs_batchkit.image_io",
        "pfs_batchkit.apa_password",
        "pfs_batchkit.workflows",
        "pfs_batchkit.cli",
        "pfs_batchkit.host",
        "pfs_batchkit.host.detect",
        "pfs_batchkit.host.runner",
        "pfs_batchkit.host.exfat",
        "pfs_batchkit.host.exfat_linux",
        "pfs_batchkit.host.exfat_darwin",
        "pfs_batchkit.host.exfat_windows",
        "pfs_batchkit.exfat_types",
        "pfs_batchkit.tui",
        "pfs_batchkit.tui_textual",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="pfs-batchkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
