#!/usr/bin/env python3
"""Minimal test runner when pytest is not installed."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pfs_batchkit import apa
from pfs_batchkit.apa_password import encrypt_empty_password
from pfs_batchkit.layout import build_boot_headers, plan_layout, patch_apaj_and_mbr_entry

REF = Path("/tmp/pfs-batchkit/mbr.img")


def test_mbr_hash():
    assert encrypt_empty_password("__mbr").hex() == "8bbd61617b39ffa5"


def test_rebuild_header():
    ref = REF.read_bytes()[:1024]
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
        created=ref[80:88],
        mbr_sony_block=ref[0x100:0x140],
    )
    assert header == ref


def test_hybrid_headers():
    layout = plan_layout(500 * 1024**3)
    headers = build_boot_headers(layout)
    assert apa.verify_apa_checksum(headers[0])
    assert headers[0][0xE0:0xE4] == apa.APAJ_MAGIC


def main():
    if not REF.is_file():
        print("skip: no reference mbr.img at", REF)
        return 0
    test_mbr_hash()
    test_rebuild_header()
    test_hybrid_headers()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
