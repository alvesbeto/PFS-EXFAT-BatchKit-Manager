"""Verify APA-Jail boot chain (FHDB / wLaunchELF KELF) after prepare."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import apa


@dataclass(frozen=True)
class BootReadyReport:
    device: Path
    kelf_present: bool
    apaj_present: bool
    mbr_signature: bool
    messages: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.kelf_present and self.apaj_present and self.mbr_signature


def _read_device(path: Path, offset: int, length: int) -> bytes:
    fd = os.open(path, os.O_RDONLY)
    try:
        return os.pread(fd, length, offset)
    finally:
        os.close(fd)


def verify_boot_ready(device: Path) -> BootReadyReport:
    """Check sector 0 APAJ/MBR and embedded loader in __mbr (BatchKit mbr.img)."""
    device = device.expanduser()
    messages: list[str] = []
    sector0 = _read_device(device, 0, apa.APA_HEADER_SIZE)

    mbr_sig = sector0[apa.MBR_SIGNATURE_OFFSET : apa.MBR_SIGNATURE_OFFSET + 2] == b"\x55\xAA"
    if mbr_sig:
        messages.append("Assinatura MBR 55 AA OK (OPL BDM seguro).")
    else:
        messages.append("FALTA assinatura MBR 55 AA — risco de corrupção no OPL.")

    apaj = sector0[0xE0 : 0xE0 + len(apa.APAJ_MAGIC)] == apa.APAJ_MAGIC
    if apaj:
        messages.append("Magic APAJ presente (APA-Jail / FHDB).")
    else:
        messages.append("Magic APAJ ausente — use mbr.img do PFS-BatchKit-Manager.")

    kelf_off = apa.OSD_MBR_MIN_KELF_SECTOR * apa.APA_SECTOR_SIZE
    kelf_head = _read_device(device, kelf_off, 64)
    kelf_present = kelf_head.startswith(b"\x7fELF") or (
        len(kelf_head) >= 4 and kelf_head[:4] not in (b"\x00\x00\x00\x00", b"\xff\xff\xff\xff")
        and any(b != 0 for b in kelf_head[:32])
    )
    if kelf_present:
        messages.append("Payload de boot detectado na região __mbr (KELF/loader BatchKit).")
    else:
        messages.append(
            "Loader __mbr ausente — aplique --reference-mbr (mbr.img GDX-X/PFS-BatchKit-Manager)."
        )

    return BootReadyReport(
        device=device,
        kelf_present=kelf_present,
        apaj_present=apaj,
        mbr_signature=mbr_sig,
        messages=tuple(messages),
    )
