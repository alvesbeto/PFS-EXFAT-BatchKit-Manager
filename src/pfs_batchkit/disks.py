"""Enumerate physical disks for PS2 HDD operations (inspired by PFS-BatchKit-Manager ScanningPS2HDD)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .host.detect import host_os

_HDL_PS2_LINE = re.compile(
    r"Playstation\s+2\s+HDD.*?(hdd\d+:)",
    re.IGNORECASE,
)
_HDL_HDD_NUM = re.compile(r"hdd(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class PhysicalDisk:
    """One writable whole-disk device."""

    index: int
    path: Path
    model: str
    size_bytes: int
    bus: str
    ps2_hdd: bool
    hdl_path: str
    mountpoints: tuple[str, ...]
    notes: str

    @property
    def size_gib(self) -> float:
        return self.size_bytes / (1024**3)

    def summary_line(self) -> str:
        ps2 = " [PS2 HDD hdl_dump]" if self.ps2_hdd else ""
        mounts = f" mounted:{','.join(self.mountpoints)}" if self.mountpoints else ""
        warn = " ⚠ DISCO DO SISTEMA — não use" if "system disk" in self.notes.lower() else ""
        return (
            f"[{self.index}] {self.path} — {self.model or 'unknown model'} "
            f"({self.size_gib:.2f} GiB){ps2}{warn}{mounts}"
        )


def _parse_size_human(text: str) -> int:
    text = text.strip().upper().replace(",", ".")
    m = re.match(r"^([\d.]+)\s*([KMGT]?)(?:IB?)?$", text)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2) or "B"
    mult = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    return int(val * mult.get(unit, 1))


def _hdl_dump_ps2_map() -> dict[int, str]:
    """Map PhysicalDrive index -> hdl_dump hddN: path (Windows BatchKit logic)."""
    exe = shutil.which("hdl_dump")
    if exe is None:
        return {}
    try:
        proc = subprocess.run(
            [exe, "query"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out = proc.stdout + proc.stderr
    mapping: dict[int, str] = {}
    for line in out.splitlines():
        if "playstation 2 hdd" not in line.lower():
            continue
        m = _HDL_HDD_NUM.search(line)
        if m:
            mapping[int(m.group(1))] = f"hdd{m.group(1)}:"
    return mapping


def _linux_mountpoints_on_disk(disk_name: str) -> tuple[str, ...]:
    """Mountpoints on partitions belonging to this whole disk (lsblk -d omits them)."""
    if not shutil.which("lsblk") or not disk_name:
        return ()
    proc = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,MOUNTPOINTS", f"/dev/{disk_name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ()
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ()
    mounts: list[str] = []

    def walk(node: dict) -> None:
        raw = node.get("mountpoints") or []
        if isinstance(raw, list):
            for mp in raw:
                if mp:
                    mounts.append(str(mp))
        elif raw:
            mounts.append(str(raw))
        for child in node.get("children") or []:
            walk(child)

    for dev in data.get("blockdevices", []):
        walk(dev)
    return tuple(dict.fromkeys(mounts))


_SYSTEM_MOUNT_PREFIXES = ("/", "/boot", "/home", "/var", "/usr")


def _mounts_indicate_system_disk(mounts: tuple[str, ...]) -> bool:
    for mp in mounts:
        if mp in _SYSTEM_MOUNT_PREFIXES:
            return True
        if mp.startswith("/boot/"):
            return True
    return False


def _sort_disks_for_selection(disks: list[PhysicalDisk]) -> list[PhysicalDisk]:
    """PS2 / USB first; disco do sistema por último (índice [N] alinhado ao BatchKit)."""

    def sort_key(d: PhysicalDisk) -> tuple[int, int, int, str]:
        system = 1 if "system disk" in d.notes.lower() else 0
        ps2 = 0 if d.ps2_hdd else 1
        removable = 0 if "removable" in d.notes.lower() else 1
        return (system, ps2, removable, str(d.path))

    ordered = sorted(disks, key=sort_key)
    return [
        PhysicalDisk(
            index=i,
            path=d.path,
            model=d.model,
            size_bytes=d.size_bytes,
            bus=d.bus,
            ps2_hdd=d.ps2_hdd,
            hdl_path=d.hdl_path,
            mountpoints=d.mountpoints,
            notes=d.notes,
        )
        for i, d in enumerate(ordered)
    ]


def _linux_disks() -> list[PhysicalDisk]:
    if shutil.which("lsblk"):
        return _linux_disks_lsblk()
    return _linux_disks_sysfs()


def _linux_disks_lsblk() -> list[PhysicalDisk]:
    proc = subprocess.run(
        [
            "lsblk",
            "-J",
            "-b",
            "-d",
            "-o",
            "NAME,PATH,SIZE,MODEL,TYPE,TRAN,RM,MOUNTPOINTS",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return _linux_disks_sysfs()
    data = json.loads(proc.stdout)
    ps2_map = _hdl_dump_ps2_map()
    disks: list[PhysicalDisk] = []
    idx = 0
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        name = dev.get("name", "")
        if name.startswith(("loop", "ram", "fd", "sr", "nbd", "md", "dm-", "zram")):
            continue
        path = Path(dev.get("path") or f"/dev/{name}")
        size = int(dev.get("size") or 0)
        model = (dev.get("model") or "").strip()
        tran = (dev.get("tran") or "").strip()
        rm = dev.get("rm") is True
        mps = dev.get("mountpoints") or []
        if isinstance(mps, list):
            mounts = tuple(str(m) for m in mps if m)
        else:
            mounts = (str(mps),) if mps else ()
        part_mounts = _linux_mountpoints_on_disk(name)
        if part_mounts:
            mounts = tuple(dict.fromkeys([*mounts, *part_mounts]))

        notes = []
        if rm:
            notes.append("removable")
        if _mounts_indicate_system_disk(mounts):
            notes.append("WARNING: system disk")

        # Match BatchKit: hddN from hdl_dump often aligns with sdX index — heuristic only on Windows.
        ps2 = False
        hdl = ""
        disks.append(
            PhysicalDisk(
                index=idx,
                path=path,
                model=model,
                size_bytes=size,
                bus=tran or "block",
                ps2_hdd=ps2,
                hdl_path=hdl,
                mountpoints=mounts,
                notes="; ".join(notes),
            )
        )
        idx += 1
    return disks


def _linux_disks_sysfs() -> list[PhysicalDisk]:
    disks: list[PhysicalDisk] = []
    idx = 0
    block = Path("/sys/block")
    if not block.is_dir():
        return disks
    for entry in sorted(block.iterdir()):
        name = entry.name
        if name.startswith(("loop", "ram", "dm-", "fd", "sr", "zram")):
            continue
        size_path = entry / "size"
        sectors = int(size_path.read_text().strip()) if size_path.is_file() else 0
        size_bytes = sectors * 512
        model_path = entry / "device" / "model"
        model = model_path.read_text().strip() if model_path.is_file() else name
        path = Path(f"/dev/{name}")
        disks.append(
            PhysicalDisk(
                index=idx,
                path=path,
                model=model,
                size_bytes=size_bytes,
                bus="block",
                ps2_hdd=False,
                hdl_path="",
                mountpoints=(),
                notes="",
            )
        )
        idx += 1
    return disks


def _windows_disks() -> list[PhysicalDisk]:
    ps2_map = _hdl_dump_ps2_map()
    script = (
        "Get-CimInstance Win32_DiskDrive | "
        "Select-Object Index,Model,Size,InterfaceType,MediaType,DeviceID | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except OSError:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    raw = json.loads(proc.stdout)
    items = raw if isinstance(raw, list) else [raw]
    disks: list[PhysicalDisk] = []
    for item in sorted(items, key=lambda x: int(x.get("Index", 0))):
        index = int(item.get("Index", 0))
        path = Path(rf"\\.\PhysicalDrive{index}")
        model = (item.get("Model") or "").strip()
        size = int(item.get("Size") or 0)
        bus = (item.get("InterfaceType") or "").strip()
        hdl = ps2_map.get(index, "")
        ps2 = index in ps2_map
        notes = "BatchKit: hdl_dump Playstation 2 HDD" if ps2 else ""
        disks.append(
            PhysicalDisk(
                index=index,
                path=path,
                model=model,
                size_bytes=size,
                bus=bus,
                ps2_hdd=ps2,
                hdl_path=hdl,
                mountpoints=(),
                notes=notes,
            )
        )
    return disks


def _darwin_disks() -> list[PhysicalDisk]:
    try:
        proc = subprocess.run(
            ["diskutil", "list", "-plist", "physical"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return []
    # Fallback: diskutil list plain text
    proc2 = subprocess.run(
        ["diskutil", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    disks: list[PhysicalDisk] = []
    idx = 0
    current: dict[str, str] = {}
    for line in (proc2.stdout or "").splitlines():
        if line.startswith("/dev/disk"):
            if current.get("path"):
                disks.append(_disk_from_darwin_dict(idx, current))
                idx += 1
            current = {"path": line.split()[0], "line": line}
        elif "GB" in line or "TB" in line:
            current["size_line"] = line.strip()
    if current.get("path"):
        disks.append(_disk_from_darwin_dict(idx, current))
    return disks


def _disk_from_darwin_dict(idx: int, data: dict[str, str]) -> PhysicalDisk:
    path = Path(data["path"].replace("/dev/disk", "/dev/rdisk"))
    line = data.get("line", "")
    model = line.split("*")[-1].strip() if "*" in line else line
    size_bytes = 0
    sl = data.get("size_line", "")
    m = re.search(r"\([\s\d.]+\s*([GT]B)\)", sl)
    if m:
        num = re.search(r"([\d.]+)\s*([GT])B", sl)
        if num:
            size_bytes = _parse_size_human(f"{num.group(1)}{num.group(2)}")
    return PhysicalDisk(
        index=idx,
        path=path,
        model=model,
        size_bytes=size_bytes,
        bus="physical",
        ps2_hdd=False,
        hdl_path="",
        mountpoints=(),
        notes="Use rdisk for raw writes",
    )


def is_likely_system_disk(device: Path) -> bool:
    """Whole-disk device that hosts Linux /, /boot, etc."""
    device = device.expanduser()
    for d in list_physical_disks():
        if d.path == device:
            return "system disk" in d.notes.lower()
    if host_os() == "linux":
        name = device.name
        if name:
            return _mounts_indicate_system_disk(_linux_mountpoints_on_disk(name))
    return False


def list_physical_disks(*, ps2_only: bool = False) -> list[PhysicalDisk]:
    os_name = host_os()
    if os_name == "windows":
        disks = _windows_disks()
    elif os_name == "darwin":
        disks = _darwin_disks()
    else:
        disks = _linux_disks()
        # Linux: mark PS2 via hdl_dump lines containing device names if we can correlate
        ps2_map = _hdl_dump_ps2_map()
        if ps2_map:
            for i, d in enumerate(disks):
                if i in ps2_map:
                    disks[i] = PhysicalDisk(
                        index=d.index,
                        path=d.path,
                        model=d.model,
                        size_bytes=d.size_bytes,
                        bus=d.bus,
                        ps2_hdd=True,
                        hdl_path=ps2_map[i],
                        mountpoints=d.mountpoints,
                        notes=(d.notes + "; hdl_dump PS2").strip("; "),
                    )

    if ps2_only:
        disks = [d for d in disks if d.ps2_hdd]
    return _sort_disks_for_selection(disks)


def resolve_disk_selection(
    selection: str,
    disks: list[PhysicalDisk] | None = None,
) -> PhysicalDisk | None:
    """Resolve list index, path, or PhysicalDriveN (BatchKit style)."""
    if disks is None:
        disks = list_physical_disks()
    sel = selection.strip()
    if not sel:
        return None

    if sel.isdigit():
        n = int(sel)
        for d in disks:
            if d.index == n:
                return d
        if host_os() == "windows":
            for d in disks:
                if d.path.name.endswith(str(n)) or str(d.path) == rf"\\.\PhysicalDrive{n}":
                    return d
        return None

    path = Path(sel)
    for d in disks:
        if d.path == path or str(d.path) == sel:
            return d
    if host_os() == "windows" and not sel.startswith(r"\\."):
        guess = Path(rf"\\.\PhysicalDrive{sel}")
        for d in disks:
            if d.path == guess:
                return d
    return None


def format_disk_listing(disks: list[PhysicalDisk]) -> list[str]:
    lines = [
        "Discos físicos (estilo PFS-BatchKit-Manager: escolha pelo número [N] ou caminho):",
        "",
    ]
    if not disks:
        lines.append("Nenhum disco encontrado.")
        return lines
    for d in disks:
        lines.append(d.summary_line())
        if d.hdl_path:
            lines.append(f"     hdl_dump: {d.hdl_path}  pfsshell/win: {d.path}")
        if d.notes:
            lines.append(f"     nota: {d.notes}")
    lines.append("")
    lines.append(
        "BatchKit usa hdl_dump query + \\\\.\\PHYSICALDRIVEN; "
        "confirme modelo/tamanho antes de gravar."
    )
    return lines
