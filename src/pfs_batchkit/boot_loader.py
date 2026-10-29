"""wLaunchELF KELF for __mbr boot (exFAT BDM on mass:/ata:).

Default (``PFS_BATCHKIT_WLAUNCHELF_EXFAT=1``): **wLaunchELF_R3Z** ``WLE-R3Z-DS34.ELF``
→ ``kelftool encrypt mbr`` (suporte **ata:/ exFAT** no HDD interno + USB exFAT).

``PFS_BATCHKIT_WLAUNCHELF_LATEST=1`` → ps2homebrew ``BOOT.ELF`` (sem garantia ata exFAT).

``PFS_BATCHKIT_WLAUNCHELF_EXFAT=0`` → ``BAT/boot.kelf`` do PFS-BatchKit-Manager.

Requer ``PS2KEYS.dat`` para builds R3Z/latest (não para boot.kelf do Manager).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .fhdb_stage import manager_root_candidates
from .wlaunchelf_config import (
    WLE_APPS_SUBDIR,
    WLE_R3Z_DS34_FILENAME,
    render_launchelf_cnf,
)

DEFAULT_BOOT_KELF = Path("/tmp/pfs-batchkit/wLaunchELF-r3z-exfat.kelf")
WLAUNCHELF_BOOT_ELF_URL = (
    "https://github.com/ps2homebrew/wLaunchELF/releases/download/latest/BOOT.ELF"
)
WLAUNCHELF_R3Z_TAG = os.environ.get("PFS_BATCHKIT_WLAUNCHELF_R3Z_TAG", "4.80")
WLAUNCHELF_R3Z_DS34_URL = (
    f"https://github.com/saildot4k/wLaunchELF_R3Z/releases/download/"
    f"{WLAUNCHELF_R3Z_TAG}/{WLE_R3Z_DS34_FILENAME}"
)
WLAUNCHELF_ISR_EXFAT_URL = (
    "https://github.com/israpps/wLaunchELF_ISR/releases/download/latest/"
    "BOOT-EXFAT-DS34-NO_NETWORK.ELF"
)
KELFTOOL_LINUX_URL = (
    "https://github.com/saildot4k/wLaunchELF_R3Z/releases/download/latest/kelftool-linux.tar.gz"
)
# keep ps2homebrew kelftool URL as fallback
KELFTOOL_LINUX_URL_PS2HB = (
    "https://github.com/ps2homebrew/kelftool/releases/download/latest/kelftool-linux.tar.gz"
)
MANAGER_BOOT_KELF_URL = (
    "https://raw.githubusercontent.com/GDX-X/PFS-BatchKit-Manager/main/"
    "PFS-BatchKit-Manager/BAT/boot.kelf"
)
BUILD_CACHE = Path("/tmp/pfs-batchkit/wLaunchELF-build")
CANONICAL_R3Z_KELF = BUILD_CACHE / "wLaunchELF-r3z-exfat.kelf"
CANONICAL_LATEST_KELF = BUILD_CACHE / "wLaunchELF-latest.kelf"


def _skip_boot_kelf_inject() -> bool:
    return os.environ.get("PFS_BATCHKIT_SKIP_BOOT_KELF", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _wlaunchelf_exfat_enabled() -> bool:
    return os.environ.get("PFS_BATCHKIT_WLAUNCHELF_EXFAT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _use_latest_wlaunchelf() -> bool:
    return os.environ.get("PFS_BATCHKIT_WLAUNCHELF_LATEST", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def resolve_ps2keys() -> Path | None:
    env = os.environ.get("PFS_BATCHKIT_PS2KEYS")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    home_keys = Path.home() / "PS2KEYS.dat"
    if home_keys.is_file():
        return home_keys
    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user and sudo_user != "root":
        for base in (Path("/home") / sudo_user, Path(f"/Users/{sudo_user}")):
            candidate = base / "PS2KEYS.dat"
            if candidate.is_file():
                return candidate
    for root in manager_root_candidates():
        for rel in ("BAT/PS2KEYS.dat", "PS2KEYS.dat"):
            candidate = root / rel
            if candidate.is_file():
                return candidate
    return None


def resolve_boot_kelf(explicit: Path | None = None) -> Path | None:
    """Output path for MBR KELF to inject after mbr.img."""
    if _skip_boot_kelf_inject():
        return None
    if explicit is not None:
        return explicit.expanduser()
    env = os.environ.get("PFS_BATCHKIT_BOOT_KELF")
    if env:
        return Path(env).expanduser()
    return DEFAULT_BOOT_KELF


def _find_kelftool() -> Path:
    env = os.environ.get("PFS_BATCHKIT_KELFTOOL")
    if env:
        p = Path(env).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return p
    repo_bin = Path(__file__).resolve().parents[2] / "tools" / "bin" / "kelftool"
    if repo_bin.is_file() and os.access(repo_bin, os.X_OK):
        return repo_bin
    cached = BUILD_CACHE / "kelftool"
    if cached.is_file() and os.access(cached, os.X_OK):
        return cached
    BUILD_CACHE.mkdir(parents=True, exist_ok=True)
    for url in (KELFTOOL_LINUX_URL_PS2HB, KELFTOOL_LINUX_URL):
        try:
            archive = BUILD_CACHE / "kelftool-linux.tar.gz"
            urllib.request.urlretrieve(url, archive)
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(BUILD_CACHE, filter="data")
            built = BUILD_CACHE / "build" / "kelftool"
            if built.is_file():
                shutil.copy2(built, cached)
                cached.chmod(0o755)
                return cached
        except (OSError, urllib.error.URLError):
            continue
    raise OSError("kelftool indisponível — defina PFS_BATCHKIT_KELFTOOL")


def _download_elf(url: str, dest: Path, *, min_bytes: int = 64 * 1024) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)
    if not dest.is_file() or dest.stat().st_size < min_bytes:
        raise OSError(f"Download ELF falhou: {dest} ({url})")


def fetch_wlaunchelf_r3z_elf() -> Path:
    """Cached WLE-R3Z-DS34.ELF (ata:/ + usb exFAT BDM)."""
    env = os.environ.get("PFS_BATCHKIT_WLAUNCHELF_ELF")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
    dest = BUILD_CACHE / WLE_R3Z_DS34_FILENAME
    if dest.is_file() and dest.stat().st_size > 64 * 1024:
        return dest
    _download_elf(WLAUNCHELF_R3Z_DS34_URL, dest)
    return dest


def _elf_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stamp_path(elf: Path) -> Path:
    return BUILD_CACHE / f"{elf.name}.sha256"


def _cache_valid(kelf: Path, elf: Path) -> bool:
    stamp = _stamp_path(elf)
    if not kelf.is_file() or kelf.stat().st_size < 64 * 1024:
        return False
    if not elf.is_file() or not stamp.is_file():
        return False
    return stamp.read_text(encoding="utf-8").strip() == _elf_sha256(elf)


def _build_kelf_from_elf(source_elf: Path, out_kelf: Path) -> None:
    keys = resolve_ps2keys()
    if keys is None:
        raise OSError(
            "PS2KEYS.dat em falta — necessário para KELF MBR (wLaunchELF R3Z/exFAT). "
            "Coloque em ~/PS2KEYS.dat ou defina PFS_BATCHKIT_PS2KEYS."
        )
    BUILD_CACHE.mkdir(parents=True, exist_ok=True)
    kelftool = _find_kelftool()
    with tempfile.TemporaryDirectory(dir=BUILD_CACHE) as td:
        work = Path(td)
        shutil.copy2(keys, work / "PS2KEYS.dat")
        shutil.copy2(source_elf, work / "BOOT.ELF")
        proc = subprocess.run(
            [str(kelftool), "encrypt", "mbr", "BOOT.ELF", "boot.kelf"],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise OSError(f"kelftool encrypt mbr falhou: {err}")
        built = work / "boot.kelf"
        if not built.is_file():
            raise OSError("kelftool não gerou boot.kelf")
        out_kelf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, out_kelf)
    _stamp_path(source_elf).write_text(_elf_sha256(source_elf), encoding="utf-8")


def _manager_boot_kelf_fallback() -> Path:
    for root in manager_root_candidates():
        for rel in ("BAT/boot.kelf", "PFS-BatchKit-Manager/BAT/boot.kelf"):
            candidate = root / rel
            if candidate.is_file():
                return candidate
    BUILD_CACHE.mkdir(parents=True, exist_ok=True)
    fallback = BUILD_CACHE / "manager-boot.kelf"
    if not fallback.is_file() or fallback.stat().st_size < 64 * 1024:
        tmp = BUILD_CACHE / "manager-boot.kelf.download"
        try:
            urllib.request.urlretrieve(MANAGER_BOOT_KELF_URL, tmp)
            tmp.replace(fallback)
        except (OSError, urllib.error.URLError) as exc:
            tmp.unlink(missing_ok=True)
            raise OSError(f"Fallback boot.kelf do Manager indisponível ({exc})") from exc
    if not fallback.is_file() or fallback.stat().st_size < 64 * 1024:
        raise OSError("Fallback boot.kelf do Manager indisponível (ficheiro inválido)")
    return fallback


def _copy_kelf_to(path: Path, canonical: Path) -> None:
    if path.resolve() != canonical.resolve():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canonical, path)


def _ensure_r3z_kelf(path: Path) -> tuple[str, ...]:
    r3z_elf = fetch_wlaunchelf_r3z_elf()
    if not _cache_valid(CANONICAL_R3Z_KELF, r3z_elf):
        _build_kelf_from_elf(r3z_elf, CANONICAL_R3Z_KELF)
    _copy_kelf_to(path, CANONICAL_R3Z_KELF)
    return (
        "Boot __mbr: wLaunchELF R3Z DS34 (ata:/ exFAT HDD + usb BDM exFAT) — "
        "github.com/saildot4k/wLaunchELF_R3Z",
    )


def _ensure_isr_exfat_kelf(path: Path) -> tuple[str, ...]:
    isr_elf = BUILD_CACHE / "BOOT-EXFAT-DS34-NO_NETWORK.ELF"
    _download_elf(WLAUNCHELF_ISR_EXFAT_URL, isr_elf)
    out = BUILD_CACHE / "wLaunchELF-isr-exfat.kelf"
    if not _cache_valid(out, isr_elf):
        _build_kelf_from_elf(isr_elf, out)
    _copy_kelf_to(path, out)
    return (
        "Boot __mbr: wLaunchELF_ISR EXFAT (USB BDM; HDD interno exFAT limitado) — fallback",
    )


def _ensure_latest_kelf(path: Path) -> tuple[str, ...]:
    boot_elf = BUILD_CACHE / "BOOT-ps2homebrew.ELF"
    _download_elf(WLAUNCHELF_BOOT_ELF_URL, boot_elf)
    if not _cache_valid(CANONICAL_LATEST_KELF, boot_elf):
        _build_kelf_from_elf(boot_elf, CANONICAL_LATEST_KELF)
    _copy_kelf_to(path, CANONICAL_LATEST_KELF)
    return (
        "Boot __mbr: wLaunchELF ps2homebrew latest "
        "(PFS_BATCHKIT_WLAUNCHELF_LATEST=1)",
    )


def ensure_boot_kelf(path: Path) -> tuple[str, ...]:
    """
    Ensure ``path`` contains MBR KELF for APA-Jail + exFAT hybrid.

    Default: R3Z exFAT build. Fallback: ISR EXFAT → Manager boot.kelf.
    """
    path = path.expanduser()
    if path.is_file() and path.stat().st_size > 64 * 1024:
        env_kelf = os.environ.get("PFS_BATCHKIT_BOOT_KELF")
        if env_kelf and Path(env_kelf).expanduser().resolve() == path.resolve():
            return (f"Boot __mbr: KELF em PFS_BATCHKIT_BOOT_KELF ({path.name})",)

    if os.environ.get("PFS_BATCHKIT_BOOT_KELF"):
        return (f"Boot __mbr: usar KELF existente em {path}",)

    if _use_latest_wlaunchelf():
        try:
            return _ensure_latest_kelf(path)
        except OSError as exc:
            return (*_manager_fallback(path), f"Aviso latest: {exc}")

    if not _wlaunchelf_exfat_enabled():
        return _manager_fallback(path)

    try:
        return _ensure_r3z_kelf(path)
    except OSError as exc:
        warnings: list[str] = [f"Aviso wLaunchELF R3Z: {exc}"]
        try:
            return (*warnings, *_ensure_isr_exfat_kelf(path))
        except OSError as exc2:
            warnings.append(f"Aviso wLaunchELF_ISR EXFAT: {exc2}")
            return (*warnings, *_manager_fallback(path))


def _manager_fallback(path: Path) -> tuple[str, ...]:
    fb = _manager_boot_kelf_fallback()
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fb, path)
    return (
        "Boot __mbr: BAT/boot.kelf do Manager "
        "(sem suporte ata:/ exFAT — use R3Z + PS2KEYS ou exFAT=1)",
    )


def stage_wlaunchelf_on_exfat(exfat_root: Path) -> tuple[str, ...]:
    """Copy R3Z ELF + LAUNCHELF.CNF to ``APPS/wLaunchELF/`` on the exFAT volume."""
    try:
        elf = fetch_wlaunchelf_r3z_elf()
    except OSError as exc:
        return (f"wLaunchELF exFAT: não copiado para APPS ({exc})",)
    wle_dir = exfat_root / "APPS" / WLE_APPS_SUBDIR
    wle_dir.mkdir(parents=True, exist_ok=True)
    dest = wle_dir / WLE_R3Z_DS34_FILENAME
    if not dest.is_file() or dest.stat().st_size != elf.stat().st_size:
        shutil.copy2(elf, dest)
    cnf = wle_dir / "LAUNCHELF.CNF"
    cnf.write_text(
        render_launchelf_cnf(cnf_dir=f"mass:/APPS/{WLE_APPS_SUBDIR}/"),
        encoding="utf-8",
    )
    _write_title_cfg(wle_dir)
    return (
        f"wLaunchELF: {WLE_R3Z_DS34_FILENAME} + LAUNCHELF.CNF em APPS/{WLE_APPS_SUBDIR}/ "
        "(ata:/ e mass: exFAT)",
    )


def _write_title_cfg(wle_dir: Path) -> None:
    (wle_dir / "title.cfg").write_text(
        f"title=wLaunchELF R3Z\nboot={WLE_R3Z_DS34_FILENAME}\nversion=1.0\n",
        encoding="utf-8",
    )
