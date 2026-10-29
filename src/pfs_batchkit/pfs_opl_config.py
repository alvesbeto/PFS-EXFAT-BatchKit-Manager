"""Install OPL PFS-side config (__system/OPL) — BatchKit conf_hdd + nota exFAT BDM."""

from __future__ import annotations

import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .opl_config import (
    render_conf_apps_fhdb_hybrid,
    render_conf_hdd_exfat_note,
    render_conf_hdd_pfs,
)
from .pfs_boot import PfsInitError, find_pfsshell


@dataclass(frozen=True)
class PfsOplConfigResult:
    paths: tuple[str, ...]
    messages: tuple[str, ...]


def _manager_conf_hdd() -> str | None:
    """Optional override from cloned PFS-BatchKit-Manager."""
    import os
    import urllib.request

    env = os.environ.get("PFS_BATCHKIT_MANAGER_ROOT")
    candidates: list[Path] = []
    if env:
        candidates.append(
            Path(env).expanduser()
            / "PFS-BatchKit-Manager/HDD-OSD/__common/OPL/conf_hdd.cfg"
        )
    candidates.append(
        Path.home()
        / "Documentos/dev/Repositorios/PFS-BatchKit-Manager/PFS-BatchKit-Manager/HDD-OSD/__common/OPL/conf_hdd.cfg"
    )
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    try:
        url = (
            "https://raw.githubusercontent.com/GDX-X/PFS-BatchKit-Manager/main/"
            "PFS-BatchKit-Manager/HDD-OSD/__common/OPL/conf_hdd.cfg"
        )
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def install_opl_pfs_config(
    device: Path,
    *,
    pfsshell: Path | None = None,
) -> PfsOplConfigResult:
    """
    Write ``__system/OPL/conf_hdd.cfg`` (BatchKit: ``hdd_partition=__common``) and
    nota exFAT — OPL classic HDD nao cria +OPL; jogos ficam no exFAT via BDM.
    """
    shell = find_pfsshell(pfsshell)
    if shell is None:
        raise PfsInitError("pfsshell necessario para config OPL em __system")

    conf_body = _manager_conf_hdd() or render_conf_hdd_pfs()
    note_body = render_conf_hdd_exfat_note()
    apps_body = render_conf_apps_fhdb_hybrid(include_fmcb_installer=False)

    with tempfile.TemporaryDirectory(prefix="pfs-batchkit-opl-pfs-") as td:
        tmp = Path(td)
        files = {
            "conf_hdd.cfg": conf_body if conf_body.endswith("\n") else conf_body + "\n",
            "EXFAT_BDM_LIBRARY.txt": note_body,
            "conf_apps.cfg": apps_body,
        }
        puts: list[str] = []
        for name, body in files.items():
            local = tmp / name
            local.write_text(body.replace("\n", "\r\n"), encoding="utf-8")
            puts.append(f"put {local} /OPL/{name}")

        script = "\n".join(
            [
                f"device {device.expanduser()}",
                "mount __system",
                "mkdir OPL",
                *puts,
                "umount",
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
        if proc.returncode != 0:
            raise PfsInitError(
                textwrap.dedent(
                    f"""\
                    pfsshell config OPL em __system falhou ({proc.returncode}).
                    stdout: {proc.stdout}
                    stderr: {proc.stderr}
                    """
                )
            )

    paths = (
        "__system/OPL/conf_hdd.cfg",
        "__system/OPL/EXFAT_BDM_LIBRARY.txt",
        "__system/OPL/conf_apps.cfg",
    )
    return PfsOplConfigResult(
        paths=paths,
        messages=(
            "OPL PFS: __system/OPL/conf_hdd.cfg (BatchKit hdd_partition=__common)",
            "OPL PFS: __system/OPL/conf_apps.cfg (Apps mass: — paridade FunTuna-Fork)",
            "OPL PFS: biblioteca de jogos = exFAT BDM (mass:/conf_opl.cfg)",
        ),
    )
