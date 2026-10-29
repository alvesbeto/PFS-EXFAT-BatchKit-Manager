"""Run privileged shell commands on Linux, macOS, and Windows."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Sequence

from .detect import host_os


class PrivilegeError(RuntimeError):
    pass


def is_admin() -> bool:
    if host_os() == "windows":
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def privilege_hint(action: str = "format exFAT") -> str:
    if host_os() == "windows":
        return f"{action} requires an Administrator terminal on Windows"
    return f"{action} requires root (run with sudo or as root)"


def command_prefix(*, use_sudo: bool, non_interactive: bool | None = None) -> list[str]:
    if is_admin():
        return []
    if host_os() == "windows":
        raise PrivilegeError(privilege_hint())
    if non_interactive is None:
        non_interactive = os.environ.get("PFS_BATCHKIT_SUDO_NONINTERACTIVE", "0") == "1"
    if use_sudo and shutil.which("sudo"):
        return ["sudo", "-n"] if non_interactive else ["sudo"]
    raise PrivilegeError(
        privilege_hint()
        + ". Set PFS_BATCHKIT_USE_SUDO=1 for sudo -n, or run under sudo."
    )


def run_cmd(
    cmd: Sequence[str],
    *,
    use_sudo: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    prefix = command_prefix(use_sudo=use_sudo)
    full = prefix + list(cmd)
    try:
        return subprocess.run(
            full,
            check=True,
            capture_output=True,
            text=True,
            input=input_text,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr or exc.stdout or ""
        if "senha" in msg.lower() or "password" in msg.lower():
            msg += (
                "\nRun the whole command under sudo/Administrator, "
                "not only sudo -n inside the app."
            )
        raise PrivilegeError(
            f"command failed ({exc.returncode}): {' '.join(full)}\n{msg}"
        ) from exc
