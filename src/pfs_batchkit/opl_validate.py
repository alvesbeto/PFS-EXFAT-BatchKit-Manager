"""Validate hybrid disk images against OPL BDM + exFAT requirements."""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import apa
from .image_io import device_size_bytes, is_raw_device
from .layout import plan_layout

EXFAT_OEM_NAME = b"EXFAT   "


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class Check:
    severity: Severity
    code: str
    message: str


@dataclass
class OplLayoutReport:
    image: Path
    total_bytes: int
    total_sectors: int
    checks: list[Check] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(c.severity == Severity.FAIL for c in self.checks)

    @property
    def warnings(self) -> bool:
        return any(c.severity == Severity.WARN for c in self.checks)

    def exit_code(self, *, strict: bool = False) -> int:
        if self.failed:
            return 2
        if strict and self.warnings:
            return 1
        return 0


def _read_at(path: Path, offset: int, length: int) -> bytes:
    fd = os.open(path, os.O_RDONLY)
    try:
        return os.pread(fd, length, offset)
    finally:
        os.close(fd)


def _add(checks: list[Check], severity: Severity, code: str, message: str) -> None:
    checks.append(Check(severity, code, message))


def validate_opl_layout(
    image_path: Path,
    *,
    require_exfat: bool = False,
    require_opl_dirs: bool = False,
) -> OplLayoutReport:
    """Check sector 0 / MBR / exFAT slice for OPL BDM compatibility (file or block device)."""
    image_path = image_path.expanduser().resolve()
    is_file = image_path.is_file()
    is_device = is_raw_device(image_path)
    if not is_file and not is_device:
        report = OplLayoutReport(image_path, 0, 0)
        _add(
            report.checks,
            Severity.FAIL,
            "missing",
            f"Não é ficheiro .img nem disco bruto: {image_path}",
        )
        return report

    try:
        total_bytes = image_path.stat().st_size if is_file else device_size_bytes(image_path)
    except (ValueError, OSError) as exc:
        report = OplLayoutReport(image_path, 0, 0)
        _add(report.checks, Severity.FAIL, "size", str(exc))
        return report
    if total_bytes % apa.APA_SECTOR_SIZE:
        report = OplLayoutReport(image_path, total_bytes, total_bytes // 512)
        _add(
            report.checks,
            Severity.FAIL,
            "align",
            f"Tamanho {total_bytes} não é múltiplo de 512 bytes",
        )
        return report

    total_sectors = total_bytes // apa.APA_SECTOR_SIZE
    layout = plan_layout(total_bytes)
    checks: list[Check] = []

    try:
        sector0 = _read_at(image_path, 0, apa.APA_HEADER_SIZE)
    except OSError as exc:
        report = OplLayoutReport(image_path, total_bytes, total_sectors, checks)
        _add(report.checks, Severity.FAIL, "read", str(exc))
        return report

    if len(sector0) < apa.APA_HEADER_SIZE:
        _add(checks, Severity.FAIL, "size", "Imagem demasiado pequena para cabeçalho APA")
        return OplLayoutReport(image_path, total_bytes, total_sectors, checks)

    # OPL hddDetectNonSonyFileSystem: MBR signature in first sector
    if sector0[apa.MBR_SIGNATURE_OFFSET : apa.MBR_SIGNATURE_OFFSET + 2] == b"\x55\xAA":
        _add(checks, Severity.OK, "mbr_sig", "Assinatura MBR 55 AA @ 0x1FE (OPL evita carregar APA/PFS)")
    else:
        _add(
            checks,
            Severity.FAIL,
            "mbr_sig",
            "Falta 55 AA @ 0x1FE — OPL pode carregar PFS e corromper o disco",
        )

    if sector0[0xE0 : 0xE0 + len(apa.APAJ_MAGIC)] == apa.APAJ_MAGIC:
        _add(checks, Severity.OK, "apaj", "Magic APAJ @ 0xE0 (APA-Jail / FHDB)")
    else:
        _add(checks, Severity.WARN, "apaj", "Magic APAJ ausente @ 0xE0")

    apa_magic = struct.unpack_from("<I", sector0, 4)[0]
    if apa_magic == apa.APA_MAGIC:
        _add(checks, Severity.OK, "apa_magic", "Magic APA @ offset 4")
        if apa.verify_apa_checksum(sector0[: apa.APA_HEADER_SIZE]):
            _add(checks, Severity.OK, "apa_sum", "Checksum APA setor 0 OK")
        else:
            _add(checks, Severity.WARN, "apa_sum", "Checksum APA setor 0 inválido")
    else:
        _add(checks, Severity.WARN, "apa_magic", f"Magic APA inesperado: 0x{apa_magic:08X}")

    entry = sector0[apa.MBR_PARTITION_ENTRY_OFFSET : apa.MBR_PARTITION_ENTRY_OFFSET + 16]
    if len(entry) != 16 or entry == bytes(16):
        _add(checks, Severity.FAIL, "mbr_entry", "Entrada MBR primária vazia @ 0x1BE")
    else:
        os_type = entry[4]
        start_lba, count = struct.unpack_from("<II", entry, 8)
        _add(
            checks,
            Severity.OK if start_lba == layout.exfat_start_sector else Severity.FAIL,
            "mbr_start",
            f"LBA início partição: {start_lba} (esperado {layout.exfat_start_sector})",
        )
        _add(
            checks,
            Severity.OK if count == layout.exfat_sector_count else Severity.FAIL,
            "mbr_count",
            f"Setores partição: {count} (esperado {layout.exfat_sector_count})",
        )
        expected_type = apa.MBR_EXFAT_TYPE
        if os_type == expected_type:
            _add(checks, Severity.OK, "mbr_type", f"Tipo partição 0x{os_type:02X} (exFAT/NTFS/exFAT class)")
        else:
            _add(
                checks,
                Severity.WARN,
                "mbr_type",
                f"Tipo partição 0x{os_type:02X} (esperado 0x{expected_type:02X})",
            )
        if start_lba + count == total_sectors:
            _add(checks, Severity.OK, "mbr_tail", "Partição exFAT termina no fim do disco")
        else:
            _add(
                checks,
                Severity.FAIL,
                "mbr_tail",
                f"start+count={start_lba + count} ≠ total={total_sectors}",
            )
        if start_lba < layout.boot_end_sector:
            _add(
                checks,
                Severity.FAIL,
                "overlap",
                "Partição exFAT sobrepõe região APA boot",
            )
        else:
            _add(
                checks,
                Severity.OK,
                "apa_gap",
                f"Região APA: 0–{layout.boot_end_sector - 1} setores "
                f"({layout.boot_end_sector * 512 // (1024 * 1024)} MiB)",
            )

    exfat_off = layout.exfat_start_sector * apa.APA_SECTOR_SIZE
    try:
        boot_sec = _read_at(image_path, exfat_off, 512)
    except OSError as exc:
        _add(checks, Severity.FAIL, "exfat_read", str(exc))
        boot_sec = b""

    if boot_sec:
        oem = boot_sec[3:11]
        if oem == EXFAT_OEM_NAME:
            _add(checks, Severity.OK, "exfat_bpb", "Superblock exFAT detectado no início da partição")
        elif boot_sec == bytes(512):
            sev = Severity.FAIL if require_exfat else Severity.WARN
            _add(
                checks,
                sev,
                "exfat_bpb",
                "Partição exFAT ainda não formatada (região zerada)",
            )
        else:
            sev = Severity.FAIL if require_exfat else Severity.WARN
            _add(
                checks,
                sev,
                "exfat_bpb",
                f"OEM name inesperado {oem!r} (esperado EXFAT)",
            )

    if require_opl_dirs:
        _add(
            checks,
            Severity.WARN,
            "opl_dirs",
            "Verificação de pastas OPL no exFAT requer montagem — use scaffold-opl ou inspecione no PC",
        )

    _add(
        checks,
        Severity.OK,
        "opl_hint",
        "No PS2: activar BDM HDD (GPT/MBR) e jogos em massN: (ícone hdd_bd), não modo HDLoader PFS",
    )

    return OplLayoutReport(image_path, total_bytes, total_sectors, checks)


def format_report(report: OplLayoutReport) -> list[str]:
    lines = [
        f"Imagem: {report.image}",
        f"Tamanho: {report.total_bytes} bytes ({report.total_sectors} setores, "
        f"{report.total_bytes / (1024**3):.2f} GiB)",
        "",
    ]
    icons = {Severity.OK: "OK", Severity.WARN: "AVISO", Severity.FAIL: "FALHA"}
    for c in report.checks:
        lines.append(f"[{icons[c.severity]}] {c.code}: {c.message}")
    lines.append("")
    if report.failed:
        lines.append("Resultado: INCOMPATÍVEL com OPL BDM/exFAT (corrigir falhas).")
    elif report.warnings:
        lines.append("Resultado: aceitável com avisos.")
    else:
        lines.append("Resultado: compatível com OPL BDM/exFAT (layout).")
    return lines
