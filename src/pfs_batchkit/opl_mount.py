"""Locate mounted exFAT volume root for OPL (volume label PS2OPL by default)."""

from __future__ import annotations

import os
from pathlib import Path

from .disks import PhysicalDisk
from .exfat_types import DEFAULT_VOLUME_LABEL
from .opl import verify_opl_tree


def _login_user() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or "user"


def opl_root_candidate_paths(
    volume_label: str = DEFAULT_VOLUME_LABEL,
    *,
    login_user: str | None = None,
) -> tuple[Path, ...]:
    """Common mount paths for a labeled exFAT volume (Linux, macOS, generic)."""
    user = login_user or _login_user()
    return (
        Path(f"/run/media/{user}/{volume_label}"),
        Path(f"/media/{user}/{volume_label}"),
        Path(f"/mnt/{volume_label}"),
        Path(f"/Volumes/{volume_label}"),
        Path(f"/media/{volume_label}"),
    )


def _ordered_mount_candidates(
    *,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    disk: PhysicalDisk | None = None,
    extra_paths: tuple[Path, ...] = (),
) -> list[Path]:
    ordered: list[Path] = []
    for raw in extra_paths:
        ordered.append(raw.expanduser())
    if disk is not None:
        for mp in disk.mountpoints:
            ordered.append(Path(mp))
            ordered.append(Path(mp) / volume_label)
    ordered.extend(opl_root_candidate_paths(volume_label))
    return ordered


def discover_exfat_volume_root(
    *,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    disk: PhysicalDisk | None = None,
    extra_paths: tuple[Path, ...] = (),
) -> Path | None:
    """First existing directory that is (or could be) the exFAT volume mount — OPL tree optional."""
    seen: set[Path] = set()
    for path in _ordered_mount_candidates(
        volume_label=volume_label,
        disk=disk,
        extra_paths=extra_paths,
    ):
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_dir():
            return resolved
    return None


def discover_opl_root(
    *,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    disk: PhysicalDisk | None = None,
    extra_paths: tuple[Path, ...] = (),
) -> Path | None:
    """
    Return the first path that looks like a prepared OPL library root (CD/, DVD/, …).

    Checks explicit hints, then mountpoints on the selected disk, then typical OS paths.
    """
    seen: set[Path] = set()
    for path in _ordered_mount_candidates(
        volume_label=volume_label,
        disk=disk,
        extra_paths=extra_paths,
    ):
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_dir():
            continue
        ok, _missing = verify_opl_tree(resolved)
        if ok:
            return resolved
    return None


def resolve_scaffold_mount(
    preferred: Path,
    *,
    disk: PhysicalDisk | None = None,
    volume_label: str = DEFAULT_VOLUME_LABEL,
) -> tuple[Path | None, list[str]]:
    """
    Resolve mount point for scaffold-opl: preferred path, else auto-detect on the selected disk / OS paths.
    """
    messages: list[str] = []
    pref = preferred.expanduser()
    if pref.is_dir():
        return pref.resolve(), messages

    found = discover_exfat_volume_root(
        volume_label=volume_label,
        disk=disk,
        extra_paths=(pref,),
    )
    if found is not None:
        messages.append(
            f"Pasta {pref} não existe; usando volume exFAT montado em {found}"
        )
        return found, messages

    hint = persistent_opl_mount_path(volume_label)
    messages.append(
        f"Pasta montada não encontrada: {pref}. "
        f"Monte o volume exFAT «{volume_label}» (ex.: {hint} ou "
        f"/run/media/$USER/{volume_label}) ou use «Preparar HDD» — "
        f"ele já cria CD/, DVD/, … no exFAT."
    )
    return None, messages


def suggest_opl_root_path(
    volume_label: str = DEFAULT_VOLUME_LABEL,
    *,
    disk: PhysicalDisk | None = None,
) -> Path:
    """Best path to show in the UI: discovered mount or the usual Linux location."""
    found = discover_opl_root(volume_label=volume_label, disk=disk)
    if found is not None:
        return found
    return persistent_opl_mount_path(volume_label)


OPL_MOUNT_MESSAGE_PREFIX = "OPL_MOUNT:"


def opl_mount_message(path: Path) -> str:
    return f"{OPL_MOUNT_MESSAGE_PREFIX}{path}"


def parse_opl_mount_message(line: str) -> Path | None:
    if line.startswith(OPL_MOUNT_MESSAGE_PREFIX):
        return Path(line[len(OPL_MOUNT_MESSAGE_PREFIX) :].strip())
    return None


def persistent_opl_mount_path(volume_label: str = DEFAULT_VOLUME_LABEL) -> Path:
    """
    Target path for remounting exFAT after prepare-device (Linux sudo UI).

    Stable under /mnt so root-assisted prepare leaves the volume ready for game copy.
    """
    return Path(f"/mnt/{volume_label}")
