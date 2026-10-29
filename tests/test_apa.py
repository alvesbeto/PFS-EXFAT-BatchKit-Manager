"""Tests for APA header generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from pfs_batchkit import apa
from pfs_batchkit.apa_password import encrypt_empty_password
from pfs_batchkit.layout import build_boot_headers, plan_layout, patch_apaj_and_mbr_entry


REFERENCE = Path("/tmp/pfs-batchkit/mbr.img")


@pytest.fixture(scope="module")
def reference_mbr() -> bytes:
    if not REFERENCE.is_file():
        pytest.skip("Download reference with: curl -o /tmp/pfs-batchkit/mbr.img ...")
    return REFERENCE.read_bytes()[:1024]


def test_mbr_empty_password_hash():
    assert encrypt_empty_password("__mbr").hex() == "8bbd61617b39ffa5"


def test_rebuild_mbr_header_first_kb(reference_mbr: bytes):
    spec = apa.ApaPartitionSpec(
        "__mbr",
        0,
        apa.mib_to_sectors(128),
        apa.APA_TYPE_MBR,
        next_sector=0,
        prev_sector=0,
    )
    pw = encrypt_empty_password("__mbr")
    header = apa.build_apa_header(
        spec,
        rpwd=pw,
        fpwd=pw,
        created=reference_mbr[80:88],
        mbr_sony_block=reference_mbr[0x100:0x140],
    )
    assert header == reference_mbr


def test_apa_checksum_roundtrip():
    layout = plan_layout(500 * 1024**3)
    headers = build_boot_headers(layout)
    mbr = headers[0]
    assert apa.verify_apa_checksum(mbr)
    assert mbr[0xE0:0xE4] == apa.APAJ_MAGIC
    assert mbr[apa.MBR_SIGNATURE_OFFSET : apa.MBR_SIGNATURE_OFFSET + 2] == b"\x55\xAA"


def test_patch_reference_preserves_kelf_magic(reference_mbr: bytes):
    layout = plan_layout(500 * 1024**3)
    image = bytearray(500 * 1024**3)
    image[: len(reference_mbr)] = reference_mbr[: apa.APA_MIB]
    patch_apaj_and_mbr_entry(image, layout)
    assert image[0xE0:0xE4] == apa.APAJ_MAGIC
    assert apa.verify_apa_checksum(bytes(image[:1024]))
