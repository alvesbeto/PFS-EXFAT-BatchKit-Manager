"""Destructive disk operations and elevation helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .detect import host_os
from .runner import is_admin


def effective_user_home() -> Path:
    """Home for UI defaults when the process runs under sudo (Path.home() → /root)."""
    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user and sudo_user != "root":
        for base in (Path("/home") / sudo_user, Path(f"/Users/{sudo_user}")):
            if base.is_dir():
                return base
    return Path.home()


def destructive_write_confirmed(*, force: bool) -> bool:
    """User confirmed (--force / UI checkbox) and safety gate passed."""
    if not force:
        return False
    if os.environ.get("PFS_BATCHKIT_ALLOW_WRITE") == "1":
        return True
    if is_admin():
        return True
    return False


def assert_destructive_write(*, force: bool) -> None:
    if not force:
        raise RuntimeError("Refusing to write a block device without --force")
    if destructive_write_confirmed(force=True):
        return
    raise RuntimeError(
        "Confirmação necessária para gravar em disco físico. "
        "No terminal: export PFS_BATCHKIT_ALLOW_WRITE=1 (com --force), "
        "ou execute como root/Administrator (ex.: sudo ./pfs-batchkit-ui)."
    )


def grant_destructive_write_in_process() -> None:
    """After explicit UI confirmation — same safety as the env var for this process."""
    os.environ["PFS_BATCHKIT_ALLOW_WRITE"] = "1"


def resolve_cli_command() -> list[str]:
    """Argv prefix to invoke pfs-batchkit CLI (PyInstaller sibling or module)."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        name = "pfs-batchkit.exe" if host_os() == "windows" else "pfs-batchkit"
        cli = exe_dir / name
        if cli.is_file():
            return [str(cli)]
        return [str(sys.executable)]
    return [sys.executable, "-m", "pfs_batchkit.cli"]


def invoke_cli_elevated(
    cli_args: list[str],
    *,
    password: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run pfs-batchkit CLI under sudo -S (Linux) or elevated shell (best effort)."""
    env_pairs = ["PFS_BATCHKIT_ALLOW_WRITE=1"]
    if extra_env:
        env_pairs.extend(f"{k}={v}" for k, v in extra_env.items())
    base = resolve_cli_command()
    if host_os() == "windows":
        raise RuntimeError(
            "Elevação interativa no Windows: abra o terminal como Administrador "
            "e execute pfs-batchkit-ui de novo."
        )
    sudo = shutil.which("sudo")
    if sudo is None:
        raise RuntimeError("sudo não encontrado; execute o app como root.")
    full = [sudo, "-S", "-E", "env", *env_pairs, *base, *cli_args]
    return subprocess.run(
        full,
        input=password + "\n",
        capture_output=True,
        text=True,
        check=False,
    )


def elevation_hint_short() -> str:
    if is_admin():
        return "Privilégios elevados: OK."
    if host_os() == "windows":
        return "Execute o terminal como Administrador para gravar discos."
    return (
        "Gravar/preparar disco: use sudo ./pfs-batchkit-ui "
        "ou informe a senha sudo na tela da operação."
    )
