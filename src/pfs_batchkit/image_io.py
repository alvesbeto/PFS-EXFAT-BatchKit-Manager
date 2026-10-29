"""Write hybrid images to files or block devices."""

from __future__ import annotations

import fcntl
import os
import stat
import struct
import subprocess
import sys
from pathlib import Path

from . import apa
from .layout import HybridLayout, build_image_file, plan_layout, _populate_boot_region


def is_block_device(path: Path) -> bool:
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    return stat.S_ISBLK(mode)


def is_raw_device(path: Path) -> bool:
    if sys.platform == "win32":
        s = str(path)
        return s.startswith(r"\\.\\") and (
            "PhysicalDrive" in s or "Harddisk" in s or "Volume" in s
        )
    if sys.platform == "darwin":
        s = str(path)
        return s.startswith("/dev/r") or is_block_device(path)
    return is_block_device(path)


def device_size_bytes(path: Path) -> int:
    """Whole-disk size in bytes (block device or raw image file)."""
    path = path.expanduser()
    if path.is_file():
        size = path.stat().st_size
        if size <= 0:
            raise ValueError(f"empty file: {path}")
        return size - (size % apa.APA_SECTOR_SIZE)

    if not is_raw_device(path):
        raise ValueError(f"not a raw device or image: {path}")

    if sys.platform == "win32":
        from .disks import list_physical_disks

        for d in list_physical_disks():
            if d.path == path or str(d.path).lower() == str(path).lower():
                if d.size_bytes > 0:
                    return d.size_bytes - (d.size_bytes % apa.APA_SECTOR_SIZE)
        raise ValueError(f"could not determine size for {path} (run list-disks)")

    if shutil_which("blockdev"):
        proc = subprocess.run(
            ["blockdev", "--getsize64", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip().isdigit():
            size = int(proc.stdout.strip())
            return size - (size % apa.APA_SECTOR_SIZE)

    if sys.platform == "linux":
        fd = os.open(path, os.O_RDONLY)
        try:
            buf = fcntl.ioctl(fd, 0x80081272, b"\0" * 8)  # BLKGETSIZE64
            size = struct.unpack("Q", buf)[0]
            return size - (size % apa.APA_SECTOR_SIZE)
        finally:
            os.close(fd)

    if sys.platform == "darwin":
        proc = subprocess.run(
            ["diskutil", "info", "-plist", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and "Total Size" in proc.stdout:
            m = __import__("re").search(
                r"<key>Total Size</key>\s*<integer>(\d+)</integer>",
                proc.stdout,
            )
            if m:
                size = int(m.group(1))
                return size - (size % apa.APA_SECTOR_SIZE)

    st = path.stat()
    if st.st_size > 0:
        return st.st_size - (st.st_size % apa.APA_SECTOR_SIZE)
    raise ValueError(f"could not determine device size: {path}")


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


from .host.privileges import assert_destructive_write


def write_boot_region_to_device(
    device: Path,
    *,
    reference_mbr: Path | None = None,
    boot_kelf: Path | None = None,
    force: bool = False,
) -> HybridLayout:
    """Write APA boot chain (384 MiB) using the disk's real capacity for MBR/exFAT layout."""
    if not is_raw_device(device):
        raise ValueError(f"not a raw block device: {device}")
    assert_destructive_write(force=force)

    total_bytes = device_size_bytes(device)
    layout = plan_layout(total_bytes)
    boot_bytes = layout.boot_end_sector * apa.APA_SECTOR_SIZE
    boot = bytearray(boot_bytes)
    _populate_boot_region(
        boot,
        layout,
        reference_mbr_path=reference_mbr,
        boot_kelf=boot_kelf,
    )

    fd = os.open(device, os.O_RDWR)
    try:
        os.pwrite(fd, bytes(boot), 0)
    finally:
        os.close(fd)
    return layout


def write_image_file(output: Path, data: bytes) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        f.write(data)


def build_and_save(
    output: Path,
    size_gib: float,
    *,
    reference_mbr: Path | None = None,
    boot_kelf: Path | None = None,
) -> HybridLayout:
    total = int(size_gib * (1024**3))
    total = (total // 512) * 512
    layout = plan_layout(total)
    build_image_file(
        output,
        total,
        reference_mbr_path=reference_mbr,
        boot_kelf=boot_kelf,
    )
    return layout
