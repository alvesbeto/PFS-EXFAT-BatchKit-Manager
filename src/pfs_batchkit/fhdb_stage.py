"""Optional FHDB / HDD-OSD file staging on PFS via pfsshell (Manager parity on PC)."""

from __future__ import annotations

import os
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .pfs_boot import PfsInitError, find_pfsshell


@dataclass(frozen=True)
class FhdbPayloadResult:
    installed_files: tuple[str, ...]
    messages: tuple[str, ...]


def _skip_auto_hdd_osd() -> bool:
    return os.environ.get("PFS_BATCHKIT_SKIP_HDD_OSD", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def manager_root_candidates() -> tuple[Path, ...]:
    env = os.environ.get("PFS_BATCHKIT_MANAGER_ROOT")
    roots: list[Path] = []
    if env:
        roots.append(Path(env).expanduser())
    roots.extend(
        (
            Path.home() / "PFS-BatchKit-Manager",
            Path.home() / "Documentos/dev/Repositorios/PFS-BatchKit-Manager",
            Path(__file__).resolve().parents[3] / "PFS-BatchKit-Manager",
        )
    )
    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        for base in (root, root / "PFS-BatchKit-Manager"):
            try:
                resolved = base.expanduser().resolve()
            except OSError:
                continue
            if resolved in seen or not resolved.is_dir():
                continue
            seen.add(resolved)
            out.append(resolved)
    return tuple(out)


def manager_hdd_osd_dirs() -> tuple[Path | None, Path | None]:
    """Local ``HDD-OSD/__system`` and ``__sysconf`` trees (same layout as Manager Install HDD-OSD)."""
    for root in manager_root_candidates():
        hdd_osd = root / "HDD-OSD"
        system = hdd_osd / "__system"
        sysconf = hdd_osd / "__sysconf"
        if system.is_dir() and _hdd_osd_system_ready(system):
            conf = sysconf if sysconf.is_dir() and any(sysconf.rglob("*")) else None
            return system, conf
    return None, None


def _hdd_osd_system_ready(system: Path) -> bool:
    """Manager detects FreeHDBoot via osdmain.elf; HDD-OSD via hosdsys.elf."""
    markers = (
        system / "osd" / "osdmain.elf",
        system / "osd100" / "hosdsys.elf",
    )
    return any(p.is_file() for p in markers)


def fhdb_payload_dir() -> Path | None:
    env = os.environ.get("PFS_BATCHKIT_FHDB_PAYLOAD")
    if env:
        root = Path(env).expanduser()
        return root if root.is_dir() else None
    system, _sysconf = manager_hdd_osd_dirs()
    return system


def _collect_files(local_root: Path) -> list[Path]:
    return sorted(p for p in local_root.rglob("*") if p.is_file())


def _mkdir_lines(local_root: Path, files: list[Path]) -> list[str]:
    dirs: set[str] = set()
    for f in files:
        rel = f.relative_to(local_root)
        if len(rel.parts) <= 1:
            continue
        for i in range(1, len(rel.parts)):
            dirs.add("/".join(rel.parts[:i]))
    return [f"mkdir {d}" for d in sorted(dirs, key=lambda x: (x.count("/"), x))]


def _upload_tree(
    device: Path,
    mount: str,
    local_root: Path,
    shell: Path,
) -> tuple[tuple[str, ...], str | None]:
    files = _collect_files(local_root)
    if not files:
        return (), f"{local_root}: sem ficheiros"

    lines = [f"device {device.expanduser()}", f"mount {mount}"]
    lines.extend(_mkdir_lines(local_root, files))
    installed: list[str] = []
    for f in files:
        rel = f.relative_to(local_root).as_posix()
        lines.append(f'put "{f}" /{rel}')
        installed.append(f"{mount}:/{rel}")
    lines.extend(["umount", "exit"])
    script = "\n".join(lines) + "\n"
    proc = subprocess.run(
        [str(shell)],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return tuple(installed), textwrap.dedent(
            f"""\
            pfsshell upload {mount} falhou ({proc.returncode}).
            stdout: {proc.stdout}
            stderr: {proc.stderr}
            """
        )
    return tuple(installed), None


def install_fhdb_payload_to_system(
    device: Path,
    payload_root: Path | None = None,
) -> FhdbPayloadResult:
    """
    Copy all files from payload_root into PFS ``__system:/`` (root).

    Use when you have a pre-built __system tree (backup). Normal flow: FMCBInstaller on PS2.
    """
    payload = payload_root or fhdb_payload_dir()
    if payload is None:
        return FhdbPayloadResult((), ("FHDB/HDD-OSD: pasta __system não configurada (opcional).",))

    shell = find_pfsshell()
    if shell is None:
        raise PfsInitError("pfsshell necessário para instalar payload FHDB em __system")

    installed, err = _upload_tree(device, "__system", payload, shell)
    if err:
        raise PfsInitError(err)
    return FhdbPayloadResult(
        installed,
        (f"FHDB: {len(installed)} ficheiro(s) em __system a partir de {payload}",),
    )


def install_manager_hdd_osd(device: Path) -> FhdbPayloadResult:
    """
    Mirror PFS-BatchKit-Manager «Install HDD-OSD»: inject ``HDD-OSD/__sysconf`` and
    ``HDD-OSD/__system`` from the Manager folder on this PC (no PS2 FMCBInstaller).
    """
    if _skip_auto_hdd_osd():
        return FhdbPayloadResult((), ("HDD-OSD: ignorado (PFS_BATCHKIT_SKIP_HDD_OSD).",))

    system, sysconf = manager_hdd_osd_dirs()
    if system is None:
        return FhdbPayloadResult(
            (),
            (
                "HDD-OSD/FHDB: clone o PFS-BatchKit-Manager e coloque os ficheiros "
                "Browser/FHDB em HDD-OSD/__system (como no Manager), ou defina "
                "PFS_BATCHKIT_FHDB_PAYLOAD / PFS_BATCHKIT_MANAGER_ROOT.",
            ),
        )

    shell = find_pfsshell()
    if shell is None:
        raise PfsInitError("pfsshell necessário para instalar HDD-OSD/FHDB no PC")

    messages: list[str] = []
    all_installed: list[str] = []

    if sysconf is not None:
        installed, err = _upload_tree(device, "__sysconf", sysconf, shell)
        if err:
            raise PfsInitError(err)
        all_installed.extend(installed)
        messages.append(
            f"HDD-OSD: {len(installed)} ficheiro(s) em __sysconf (Manager HDD-OSD/)"
        )

    installed, err = _upload_tree(device, "__system", system, shell)
    if err:
        raise PfsInitError(err)
    all_installed.extend(installed)
    if (system / "osd" / "osdmain.elf").is_file():
        messages.append(
            "FreeHDBoot: osdmain.elf injectado — boot menu OSD (sem FMCBInstaller no PS2)."
        )
    elif (system / "osd100" / "hosdsys.elf").is_file():
        messages.append("HDD-OSD: hosdsys.elf injectado (Browser 2.0).")
    messages.append(
        f"HDD-OSD: {len(installed)} ficheiro(s) em __system a partir de {system.parent}"
    )

    return FhdbPayloadResult(tuple(all_installed), tuple(messages))


def probe_fhdb_installed(device: Path) -> bool:
    """True if __system/osd/osdmain.elf exists (Manager FreeHDBoot check)."""
    shell = find_pfsshell()
    if shell is None:
        return False
    script = "\n".join(
        [
            f"device {device.expanduser()}",
            "mount __system",
            "cd osd",
            "ls",
            "exit",
            "",
        ]
    )
    proc = subprocess.run(
        [str(shell)],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    return "osdmain.elf" in proc.stdout
