"""Fetch Open PS2 Loader latest development build (GitHub releases/tag/latest)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

OPL_LATEST_DEV_ELF_URL = (
    "https://github.com/ps2homebrew/Open-PS2-Loader/releases/download/latest/OPNPS2LD.ELF"
)
OPL_LATEST_RELEASE_API = (
    "https://api.github.com/repos/ps2homebrew/Open-PS2-Loader/releases/tags/latest"
)
OPL_BOOT_ELF_NAME = "OPNPS2LD.ELF"
OPL_CACHE_DIR = Path("/tmp/pfs-batchkit/opl-build")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_dev_label() -> str:
    try:
        req = urllib.request.Request(
            OPL_LATEST_RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "pfs-batchkit"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        assets = data.get("assets") or []
        for asset in assets:
            if asset.get("name") == OPL_BOOT_ELF_NAME:
                updated = asset.get("updated_at", "")[:10]
                return f"latest dev ({updated})" if updated else "latest development build"
        return "latest development build"
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return "latest development build"


def fetch_latest_opl_elf(dest: Path) -> tuple[Path | None, tuple[str, ...]]:
    """
    Copy OPNPS2LD.ELF from Open-PS2-Loader ``releases/latest`` (rolling dev build).

    Returns (path or None, log lines).
    """
    if os.environ.get("PFS_BATCHKIT_SKIP_OPL_DOWNLOAD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        if dest.is_file() and dest.stat().st_size > 64 * 1024:
            return dest, ("OPL: download desactivado (ficheiro local).",)
        return None, ("OPL: PFS_BATCHKIT_SKIP_OPL_DOWNLOAD sem OPNPS2LD.ELF local.",)

    env_elf = os.environ.get("PFS_BATCHKIT_OPL_ELF")
    if env_elf:
        src = Path(env_elf).expanduser()
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return dest, (f"OPL: {src.name} (PFS_BATCHKIT_OPL_ELF)",)

    OPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    canonical = OPL_CACHE_DIR / OPL_BOOT_ELF_NAME
    stamp = OPL_CACHE_DIR / f"{OPL_BOOT_ELF_NAME}.sha256"
    tmp = OPL_CACHE_DIR / f"{OPL_BOOT_ELF_NAME}.download"

    try:
        urllib.request.urlretrieve(OPL_LATEST_DEV_ELF_URL, tmp)
    except (OSError, urllib.error.URLError) as exc:
        if dest.is_file() and dest.stat().st_size > 64 * 1024:
            return dest, (f"OPL: offline — a usar {dest.name} local ({exc})",)
        return None, (f"OPL: download falhou ({exc})",)

    if not tmp.is_file() or tmp.stat().st_size < 64 * 1024:
        return None, ("OPL: OPNPS2LD.ELF inválido após download.",)

    digest = _sha256(tmp)
    cache_hit = (
        stamp.is_file()
        and stamp.read_text(encoding="utf-8").strip() == digest
        and canonical.is_file()
    )
    if cache_hit:
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(canonical)
        stamp.write_text(digest, encoding="utf-8")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(canonical, dest)

    if cache_hit:
        return dest, (
            f"OPL: Open-PS2-Loader latest development build (cache OK) → APPS/OPL/{OPL_BOOT_ELF_NAME}",
        )
    label = _latest_dev_label()
    return dest, (
        f"OPL: Open-PS2-Loader {label} → APPS/OPL/{OPL_BOOT_ELF_NAME}",
    )
