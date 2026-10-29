"""APA partition headers (PS2 SDK libapa layout, 1024 bytes)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

APA_MAGIC = 0x00415041
APA_HEADER_SIZE = 1024
APA_SECTOR_SIZE = 512
APA_MIB = 128 * 1024 * 1024
APA_MIB_SECTORS = APA_MIB // APA_SECTOR_SIZE  # 262144

APA_TYPE_MBR = 0x0001
APA_TYPE_PFS = 0x0100

SONY_MBR_MAGIC = b"Sony Computer Entertainment Inc."
APAJ_MAGIC = b"APAJ"

MBR_PARTITION_ENTRY_OFFSET = 0x1BE
MBR_SIGNATURE_OFFSET = 0x1FE
MBR_EXFAT_TYPE = 0x07

# Offsets in sector 0 (same as hddSetOsdMBR / PSX-Place MBR KELF notes)
OSD_MBR_START_SECTOR_OFFSET = 0x130
OSD_MBR_SIZE_SECTORS_OFFSET = 0x134
OSD_MBR_MIN_KELF_SECTOR = 16


@dataclass(frozen=True)
class ApaPartitionSpec:
    name: str
    start_sector: int
    length_sectors: int
    part_type: int
    flags: int = 0
    next_sector: int = 0
    prev_sector: int = 0


def mib_to_sectors(mib: int) -> int:
    return (mib * 1024 * 1024) // APA_SECTOR_SIZE


def apa_checksum(header: bytes) -> int:
    if len(header) != APA_HEADER_SIZE:
        raise ValueError("APA header must be 1024 bytes")
    words = struct.unpack("<256I", header)
    return sum(words[1:256]) & 0xFFFFFFFF


def verify_apa_checksum(header: bytes) -> bool:
    words = struct.unpack("<256I", header)
    return words[0] == apa_checksum(header)


def _pack_ps2_time(when: datetime | None = None) -> bytes:
    when = when or datetime.now(timezone.utc)
    return struct.pack(
        "<BBBBBBH",
        0,
        when.second,
        when.minute,
        when.hour,
        when.day,
        when.month,
        when.year,
    )


def build_apa_header(
    spec: ApaPartitionSpec,
    *,
    rpwd: bytes | None = None,
    fpwd: bytes | None = None,
    created: bytes | None = None,
    mbr_sony_block: bytes | None = None,
    osd_start_sector: int | None = None,
    osd_size_sectors: int | None = None,
    apaj: bool = False,
    mbr_primary_entry: bytes | None = None,
) -> bytes:
    """Build a 1024-byte APA header; checksum is computed last."""
    from .apa_password import encrypt_empty_password

    if len(spec.name) >= 32:
        raise ValueError("partition name too long")
    if rpwd is None:
        rpwd = encrypt_empty_password(spec.name)
    if fpwd is None:
        fpwd = encrypt_empty_password(spec.name)
    if len(rpwd) != 8 or len(fpwd) != 8:
        raise ValueError("APA passwords are 8 bytes")

    buf = bytearray(APA_HEADER_SIZE)
    struct.pack_into("<I", buf, 4, APA_MAGIC)
    struct.pack_into("<I", buf, 8, spec.next_sector)
    struct.pack_into("<I", buf, 12, spec.prev_sector)
    buf[16 : 16 + len(spec.name)] = spec.name.encode("ascii")
    buf[48:56] = rpwd[:8]
    buf[56:64] = fpwd[:8]
    struct.pack_into("<I", buf, 64, spec.start_sector)
    struct.pack_into("<I", buf, 68, spec.length_sectors)
    struct.pack_into("<H", buf, 72, spec.part_type)
    struct.pack_into("<H", buf, 74, spec.flags)
    struct.pack_into("<I", buf, 76, 0)  # nsub

    created_bytes = created or _pack_ps2_time()
    buf[80:88] = created_bytes[:8]

    # mbr sub-struct at offset 0x100
    mbr_off = 0x100
    if mbr_sony_block is not None:
        buf[mbr_off : mbr_off + len(mbr_sony_block)] = mbr_sony_block
    else:
        magic = SONY_MBR_MAGIC
        buf[mbr_off : mbr_off + len(magic)] = magic
        struct.pack_into("<I", buf, mbr_off + 0x20, 2)  # version
        if osd_start_sector is not None:
            struct.pack_into("<I", buf, OSD_MBR_START_SECTOR_OFFSET, osd_start_sector)
        if osd_size_sectors is not None:
            struct.pack_into("<I", buf, OSD_MBR_SIZE_SECTORS_OFFSET, osd_size_sectors)

    if apaj:
        buf[0xE0 : 0xE0 + len(APAJ_MAGIC)] = APAJ_MAGIC

    if mbr_primary_entry is not None:
        if len(mbr_primary_entry) != 16:
            raise ValueError("MBR primary entry must be 16 bytes")
        buf[MBR_PARTITION_ENTRY_OFFSET : MBR_PARTITION_ENTRY_OFFSET + 16] = mbr_primary_entry
        buf[MBR_SIGNATURE_OFFSET : MBR_SIGNATURE_OFFSET + 2] = b"\x55\xAA"

    struct.pack_into("<I", buf, 0, apa_checksum(bytes(buf)))
    return bytes(buf)


def build_mbr_partition_entry_lba(
    start_lba: int, sector_count: int, *, bootable: bool = False, os_type: int = MBR_EXFAT_TYPE
) -> bytes:
    """Classic MBR entry (start/end CHS set to max for large disks)."""
    entry = bytearray(16)
    entry[0] = 0x80 if bootable else 0x00
    # CHS start/end placeholders (LBA-only style used on modern tools)
    entry[1:4] = bytes([254, 255, 255])
    entry[4] = os_type
    entry[5:8] = bytes([254, 255, 255])
    struct.pack_into("<I", entry, 8, start_lba)
    struct.pack_into("<I", entry, 12, sector_count)
    return bytes(entry)


def iter_boot_chain_specs() -> Iterable[ApaPartitionSpec]:
    """Minimal FHDB footprint: __mbr + __system + __sysconf (128 MiB each)."""
    s0 = 0
    s1 = mib_to_sectors(128)
    s2 = mib_to_sectors(256)
    len128 = mib_to_sectors(128)
    yield ApaPartitionSpec("__mbr", s0, len128, APA_TYPE_MBR, next_sector=s1)
    yield ApaPartitionSpec(
        "__system", s1, len128, APA_TYPE_PFS, next_sector=s2, prev_sector=s0
    )
    yield ApaPartitionSpec(
        "__sysconf", s2, len128, APA_TYPE_PFS, next_sector=0, prev_sector=s1
    )


def boot_region_end_sector() -> int:
    """First sector after the three 128 MiB APA partitions."""
    return mib_to_sectors(384)
