# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for pfs-batchkit Qt GUI (PySide6)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH).resolve().parent
src = root / "src"

pyside_datas, pyside_binaries, pyside_hidden = collect_all("PySide6")

a = Analysis(
    [str(root / "packaging" / "entry_gui.py")],
    pathex=[str(src)],
    binaries=pyside_binaries,
    datas=pyside_datas,
    hiddenimports=[
        "pfs_batchkit.apa",
        "pfs_batchkit.layout",
        "pfs_batchkit.exfat",
        "pfs_batchkit.pfs_boot",
        "pfs_batchkit.opl",
        "pfs_batchkit.image_io",
        "pfs_batchkit.apa_password",
        "pfs_batchkit.workflows",
        "pfs_batchkit.disks",
        "pfs_batchkit.gui",
        "pfs_batchkit.gui.main",
        "pfs_batchkit.gui.wizard",
        "pfs_batchkit.gui.wizard_pages",
        "pfs_batchkit.gui.opl_transfer",
        "pfs_batchkit.gui.page_ids",
        "pfs_batchkit.fhdb_bdm",
        "pfs_batchkit.fhdb_stage",
        "pfs_batchkit.opl_validate",
        "pfs_batchkit.gui.workers",
        "pfs_batchkit.gui.state",
        "pfs_batchkit.host",
        "pfs_batchkit.host.detect",
        "pfs_batchkit.host.runner",
        "pfs_batchkit.host.privileges",
        "pfs_batchkit.host.exfat",
        "pfs_batchkit.host.exfat_linux",
        "pfs_batchkit.host.exfat_darwin",
        "pfs_batchkit.host.exfat_windows",
        "pfs_batchkit.exfat_types",
        *pyside_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["textual"],
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
    name="pfs-batchkit-ui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
