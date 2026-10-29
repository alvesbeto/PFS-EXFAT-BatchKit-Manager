"""Build hybrid APA-Jail boot region + exFAT partition metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import apa
from .opl import OPL_ROOT_DIRS, write_opl_tree


@dataclass(frozen=True)
class HybridLayout:
    total_bytes: int
    boot_end_sector: int
    exfat_start_sector: int
    exfat_sector_count: int


def plan_layout(total_bytes: int) -> HybridLayout:
    if total_bytes < apa.boot_region_end_sector() * apa.APA_SECTOR_SIZE:
        raise ValueError("disk smaller than 384 MiB APA boot region")
    boot_end = apa.boot_region_end_sector()
    total_sectors = total_bytes // apa.APA_SECTOR_SIZE
    exfat_start = boot_end
    exfat_count = total_sectors - exfat_start
    if exfat_count < 2048:
        raise ValueError("exFAT region too small")
    return HybridLayout(total_bytes, boot_end, exfat_start, exfat_count)


def build_boot_headers(layout: HybridLayout) -> dict[int, bytes]:
    """Sector index -> 1024-byte APA header to write at that sector."""
    specs = list(apa.iter_boot_chain_specs())
    mbr_entry = apa.build_mbr_partition_entry_lba(
        layout.exfat_start_sector, layout.exfat_sector_count
    )
    headers: dict[int, bytes] = {}
    for i, spec in enumerate(specs):
        kwargs: dict = {}
        if spec.name == "__mbr":
            kwargs["apaj"] = True
            kwargs["mbr_primary_entry"] = mbr_entry
        if spec.name == "__system" or spec.name == "__sysconf":
            kwargs["rpwd"] = b"\x00" * 8
            kwargs["fpwd"] = b"\x00" * 8
        headers[spec.start_sector] = apa.build_apa_header(spec, **kwargs)
    return headers


def apply_reference_mbr_payload(
    image: bytearray,
    reference: bytes,
    *,
    max_copy: int | None = None,
) -> None:
    """Copy BatchKit-style __mbr region payload (header + KELF) from reference image."""
    limit = min(len(reference), len(image), max_copy or len(reference))
    image[:limit] = reference[:limit]


def patch_apaj_and_mbr_entry(image: bytearray, layout: HybridLayout) -> None:
    """Ensure sector 0 has APAJ + MBR entry pointing at exFAT (keeps reference KELF if present)."""
    import struct

    if len(image) < apa.APA_HEADER_SIZE:
        raise ValueError("image too small")
    full = bytearray(image[: apa.APA_HEADER_SIZE])
    full[0xE0 : 0xE0 + len(apa.APAJ_MAGIC)] = apa.APAJ_MAGIC
    entry = apa.build_mbr_partition_entry_lba(
        layout.exfat_start_sector, layout.exfat_sector_count
    )
    full[apa.MBR_PARTITION_ENTRY_OFFSET : apa.MBR_PARTITION_ENTRY_OFFSET + 16] = entry
    full[apa.MBR_SIGNATURE_OFFSET : apa.MBR_SIGNATURE_OFFSET + 2] = b"\x55\xAA"
    spec = next(apa.iter_boot_chain_specs())
    struct.pack_into("<I", full, 8, spec.next_sector)
    struct.pack_into("<I", full, 12, spec.prev_sector)
    struct.pack_into("<I", full, 0, apa.apa_checksum(bytes(full)))
    image[: apa.APA_HEADER_SIZE] = full


def write_boot_chain(image: bytearray, layout: HybridLayout) -> None:
    headers = build_boot_headers(layout)
    for sector, header in headers.items():
        off = sector * apa.APA_SECTOR_SIZE
        if off + len(header) > len(image):
            raise ValueError("boot header out of range")
        image[off : off + len(header)] = header


def build_image_bytes(
    total_bytes: int,
    *,
    reference_mbr_path: Path | None = None,
    boot_kelf: Path | None = None,
) -> bytes:
    """In-memory image (only for small sizes). Prefer build_image_file for large disks."""
    if total_bytes > 512 * 1024 * 1024:
        raise ValueError(
            "Image larger than 512 MiB: use build_image_file() for sparse disk images"
        )
    layout = plan_layout(total_bytes)
    image = bytearray(total_bytes)
    _populate_boot_region(
        image,
        layout,
        reference_mbr_path=reference_mbr_path,
        boot_kelf=boot_kelf,
    )
    return bytes(image)


def _populate_boot_region(
    image: bytearray,
    layout: HybridLayout,
    *,
    reference_mbr_path: Path | None,
    boot_kelf: Path | None,
) -> None:
    if reference_mbr_path is not None:
        ref = reference_mbr_path.read_bytes()
        apply_reference_mbr_payload(image, ref, max_copy=apa.APA_MIB)
        patch_apaj_and_mbr_entry(image, layout)
        headers = build_boot_headers(layout)
        for sector, header in headers.items():
            if sector == 0:
                continue
            off = sector * apa.APA_SECTOR_SIZE
            image[off : off + len(header)] = header
    else:
        write_boot_chain(image, layout)
    if boot_kelf is not None:
        inject_boot_kelf(image, boot_kelf)


def build_image_file(
    output: Path,
    total_bytes: int,
    *,
    reference_mbr_path: Path | None = None,
    boot_kelf: Path | None = None,
) -> HybridLayout:
    """
    Create a sparse raw disk image: APA boot (384 MiB) + exFAT uses all remaining sectors.
    """
    layout = plan_layout(total_bytes)
    if layout.exfat_start_sector * apa.APA_SECTOR_SIZE + layout.exfat_sector_count * apa.APA_SECTOR_SIZE != total_bytes:
        raise RuntimeError("layout mismatch: exFAT region must fill the disk after APA boot")

    output.parent.mkdir(parents=True, exist_ok=True)
    boot_bytes = layout.boot_end_sector * apa.APA_SECTOR_SIZE
    boot = bytearray(boot_bytes)
    _populate_boot_region(
        boot,
        layout,
        reference_mbr_path=reference_mbr_path,
        boot_kelf=boot_kelf,
    )

    fd = os.open(output, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.ftruncate(fd, total_bytes)
        os.pwrite(fd, bytes(boot), 0)
    finally:
        os.close(fd)
    return layout


def inject_boot_kelf(image: bytearray, kelf_path: Path) -> None:
    data = kelf_path.read_bytes()
    start_sector = apa.OSD_MBR_MIN_KELF_SECTOR
    size_sectors = (len(data) + apa.APA_SECTOR_SIZE - 1) // apa.APA_SECTOR_SIZE
    if size_sectors > 1725:
        raise ValueError("KELF exceeds PS2 MBR loader limit (1725 sectors)")
    off = start_sector * apa.APA_SECTOR_SIZE
    if off + len(data) > apa.APA_MIB:
        raise ValueError("KELF does not fit in __mbr 128 MiB region")
    image[off : off + len(data)] = data
    header = bytearray(image[: apa.APA_HEADER_SIZE])
    __import__("struct").pack_into("<I", header, apa.OSD_MBR_START_SECTOR_OFFSET, start_sector)
    __import__("struct").pack_into("<I", header, apa.OSD_MBR_SIZE_SECTORS_OFFSET, size_sectors)
    __import__("struct").pack_into("<I", header, 0, apa.apa_checksum(bytes(header)))
    image[: apa.APA_HEADER_SIZE] = header[: apa.APA_HEADER_SIZE]


__all__ = [
    "HybridLayout",
    "plan_layout",
    "build_image_bytes",
    "build_image_file",
    "write_opl_tree",
    "OPL_ROOT_DIRS",
]
