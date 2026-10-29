"""Detect host operating system."""

from __future__ import annotations

import sys
from typing import Literal

HostOS = Literal["linux", "darwin", "windows"]


def host_os() -> HostOS:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"
