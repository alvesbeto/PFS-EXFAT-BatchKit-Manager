"""Tests for OPL layout validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pfs_batchkit import apa
from pfs_batchkit.layout import build_image_file, plan_layout
from pfs_batchkit.opl_validate import Severity, validate_opl_layout


def test_validate_fresh_hybrid_image():
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "test.img"
        layout = plan_layout(1024**3)
        build_image_file(img, layout.total_bytes)
        report = validate_opl_layout(img)
        assert not report.failed
        codes = {c.code: c.severity for c in report.checks}
        assert codes["mbr_sig"] == Severity.OK
        assert codes["apaj"] == Severity.OK
        assert codes["mbr_tail"] == Severity.OK
        assert codes["exfat_bpb"] == Severity.WARN  # not formatted yet
        assert report.exit_code(strict=False) == 0
        assert report.exit_code(strict=True) == 1


def test_validate_require_exfat_fails_unformatted():
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "test.img"
        build_image_file(img, 1024**3)
        report = validate_opl_layout(img, require_exfat=True)
        assert report.failed


def test_validate_bad_mbr_signature():
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "bad.img"
        build_image_file(img, 1024**3)
        with img.open("r+b") as f:
            f.seek(apa.MBR_SIGNATURE_OFFSET)
            f.write(b"\x00\x00")
        report = validate_opl_layout(img)
        assert report.failed
        assert any(c.code == "mbr_sig" for c in report.checks)


if __name__ == "__main__":
    test_validate_fresh_hybrid_image()
    test_validate_require_exfat_fails_unformatted()
    test_validate_bad_mbr_signature()
    print("ok")
