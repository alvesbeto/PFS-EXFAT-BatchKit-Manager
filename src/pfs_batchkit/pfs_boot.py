"""Format PFS on existing APA partitions __system / __sysconf via pfsshell."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

BOOT_PFS_PARTITIONS = ("__system", "__sysconf")


@dataclass(frozen=True)
class PfsInitResult:
    device: str
    partitions: tuple[str, ...]
    pfsshell: str


class PfsInitError(RuntimeError):
    pass


def find_pfsshell(explicit: Path | None = None) -> Path | None:
    names = ("pfsshell", "pfsshell.exe")

    def ok(p: Path) -> Path | None:
        if not p.is_file():
            return None
        if sys.platform == "win32":
            return p
        return p if os.access(p, os.X_OK) else None

    if explicit is not None:
        return ok(explicit.expanduser().resolve())

    env = os.environ.get("PFS_BATCHKIT_PFSSHELL")
    if env:
        found = ok(Path(env))
        if found:
            return found

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for name in names:
            found = ok(exe_dir / name)
            if found:
                return found

    repo_bin = Path(__file__).resolve().parents[2] / "tools" / "bin"
    for name in names:
        found = ok(repo_bin / name)
        if found:
            return found

    for name in names:
        which = shutil.which(name)
        if which:
            return Path(which)
    return None


def pfsshell_requirements_hint() -> str:
    os_hint = "Windows/macOS/Linux"
    if find_pfsshell() is not None:
        return f"OK (pfsshell with mkfs — {os_hint})"
    return (
        "Missing pfsshell; set PFS_BATCHKIT_PFSSHELL, place pfsshell next to the "
        "executable, or build tools/build_pfsshell.sh (Linux)"
    )


def _pfsshell_script(device: str, partitions: tuple[str, ...]) -> str:
    lines = [f"device {device}"]
    for name in partitions:
        lines.append(f"mkfs {name}")
    lines.append("exit")
    return "\n".join(lines) + "\n"


def init_boot_pfs_partitions(
    image_path: Path,
    *,
    pfsshell: Path | None = None,
    partitions: tuple[str, ...] = BOOT_PFS_PARTITIONS,
) -> PfsInitResult:
    """
    Run pfsshell mkfs on FHDB system partitions.

    pfsshell accepts a raw image file or block device path (no losetup required).
    Requires pfsshell built with `mkfs` (tools/build_pfsshell.sh).
    """
    shell = find_pfsshell(pfsshell)
    if shell is None:
        raise PfsInitError(pfsshell_requirements_hint())

    image_path = image_path.expanduser()
    if not image_path.exists():
        raise PfsInitError(f"image or device not found: {image_path}")

    device = str(image_path)
    script = _pfsshell_script(device, partitions)
    proc = subprocess.run(
        [str(shell)],
        input=script,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise PfsInitError(
            textwrap.dedent(
                f"""\
                pfsshell failed ({proc.returncode}).
                stdout:
                {proc.stdout}
                stderr:
                {proc.stderr}
                If mkfs is unknown, rebuild pfsshell: tools/build_pfsshell.sh
                """
            )
        )
    return PfsInitResult(
        device=device,
        partitions=partitions,
        pfsshell=str(shell),
    )


def verify_pfs_partitions_mounted(
    image_path: Path,
    *,
    pfsshell: Path | None = None,
    partitions: tuple[str, ...] = BOOT_PFS_PARTITIONS,
) -> tuple[bool, list[str]]:
    """Mount each PFS partition briefly; confirm pfsshell can access it."""
    shell = find_pfsshell(pfsshell)
    if shell is None:
        return False, [pfsshell_requirements_hint()]
    device = str(image_path.expanduser())
    lines_out: list[str] = []
    ok = True
    for part in partitions:
        script = f"device {device}\nmount {part}\nls\numount\nexit\n"
        proc = subprocess.run(
            [str(shell)],
            input=script,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            ok = False
            lines_out.append(f"PFS {part}: falha ao montar (pfsshell {proc.returncode})")
        else:
            lines_out.append(f"PFS {part}: montável (pronto para FHDB Install From HDD)")
    return ok, lines_out
