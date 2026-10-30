"""CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .exfat import DEFAULT_VOLUME_LABEL
from .workflows import (
    resolve_reference_mbr,
    run_build_image,
    run_finalize_fhdb_device,
    run_format_exfat,
    run_init_pfs,
    run_prepare_device,
    run_prepare_pfs_device,
    run_scaffold_opl,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pfs-batchkit",
        description="Build PS2 APA-Jail boot + exFAT OPL hybrid disk images",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "ui",
        help="Assistente gráfico Qt (instalador HDD PS2)",
    )

    build = sub.add_parser("build-image", help="Write a .img file (safe)")
    build.add_argument(
        "--size-gib",
        type=float,
        default=500.0,
        help="Total image size in GiB (default: 500)",
    )
    build.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for raw disk image",
    )
    build.add_argument(
        "--reference-mbr",
        type=Path,
        help="PFS-BatchKit BAT/mbr.img (copies __mbr boot payload)",
    )
    build.add_argument(
        "--boot-kelf",
        type=Path,
        help="KELF MBR custom (default: wLaunchELF latest dev build + kelftool)",
    )
    build.add_argument(
        "--format-exfat",
        action="store_true",
        help="Format exFAT on the game region (Linux, requires root/sudo)",
    )
    build.add_argument(
        "--no-opl-scaffold",
        action="store_true",
        help="With --format-exfat, skip creating CD/DVD/... folders",
    )
    build.add_argument(
        "--volume-label",
        default=DEFAULT_VOLUME_LABEL,
        help=f"exFAT volume label (default: {DEFAULT_VOLUME_LABEL})",
    )
    build.add_argument(
        "--init-pfs",
        action="store_true",
        help="Format PFS on __system and __sysconf (Linux, pfsshell+mkfs, root)",
    )
    build.add_argument(
        "--pfsshell",
        type=Path,
        help="Path to pfsshell binary (default: tools/bin or PATH)",
    )

    pfs = sub.add_parser(
        "init-pfs",
        help="Format PFS on __system / __sysconf in an existing hybrid image",
    )
    pfs.add_argument("image", type=Path)
    pfs.add_argument("--pfsshell", type=Path)

    fmt = sub.add_parser(
        "format-exfat",
        help="Format exFAT (+ optional OPL tree) on an existing hybrid image",
    )
    fmt.add_argument("image", type=Path)
    fmt.add_argument(
        "--size-gib",
        type=float,
        help="Total image size in GiB (default: infer from file size)",
    )
    fmt.add_argument("--volume-label", default=DEFAULT_VOLUME_LABEL)
    fmt.add_argument(
        "--no-opl-scaffold",
        action="store_true",
        help="Do not create OPL folder tree after format",
    )
    fmt.add_argument(
        "--force",
        action="store_true",
        help="Obrigatório em disco físico; só formata se FHDB + ATA-Assault presentes",
    )

    opl = sub.add_parser(
        "scaffold-opl",
        help="Create OPL folder tree on a mounted exFAT directory",
    )
    opl.add_argument("mount_point", type=Path)

    list_disks = sub.add_parser(
        "list-disks",
        help="List physical drives (BatchKit-style selection by index)",
    )
    list_disks.add_argument(
        "--ps2-only",
        action="store_true",
        help="Only disks reported by hdl_dump as Playstation 2 HDD",
    )

    prep = sub.add_parser(
        "prepare-device",
        help="Prepare hybrid APA+exFAT layout directly on a disk (uses real disk size)",
    )
    prep.add_argument(
        "device",
        type=Path,
        nargs="?",
        help="Block device path",
    )
    prep.add_argument(
        "--pick",
        type=int,
        metavar="N",
        help="Disk index from list-disks",
    )
    prep.add_argument(
        "--reference-mbr",
        type=Path,
        help="PFS-BatchKit BAT/mbr.img (copies __mbr boot payload)",
    )
    prep.add_argument(
        "--boot-kelf",
        type=Path,
        help="KELF MBR custom (default: wLaunchELF latest + kelftool)",
    )
    prep.add_argument(
        "--init-pfs",
        action="store_true",
        help="Format PFS on __system / __sysconf (pfsshell+mkfs)",
    )
    prep.add_argument(
        "--format-exfat",
        action="store_true",
        help=(
            "Só com PFS_BATCHKIT_FORMAT_EXFAT_ON_PREPARE=1 e FHDB+ATA-Assault no disco; "
            "caso normal: format-exfat após Install FHDB no PS2"
        ),
    )
    prep.add_argument(
        "--defer-exfat",
        action="store_true",
        help="Ignorado se FORMAT_EXFAT_ON_PREPARE não estiver activo (exFAT adiado por defeito)",
    )
    prep.add_argument(
        "--no-opl-scaffold",
        action="store_true",
        help="With --format-exfat, skip creating OPL folder tree",
    )
    prep.add_argument(
        "--cfg-dev",
        action="store_true",
        help="Create CFG-DEV instead of CFG (OPL development)",
    )
    prep.add_argument("--volume-label", default=DEFAULT_VOLUME_LABEL)
    prep.add_argument("--pfsshell", type=Path)
    prep.add_argument("--force", action="store_true")

    recover = sub.add_parser(
        "recover-first-boot",
        help=(
            "Apaga superblock exFAT (tela preta antes do wLaunchELF/FHDB) — "
            "não altera APA/PFS"
        ),
    )
    recover.add_argument("device", type=Path)
    recover.add_argument("--force", action="store_true", required=True)

    prep_pfs = sub.add_parser(
        "prepare-pfs",
        help=(
            "Reformat PFS only (__system/__sysconf): FHDB/OSD/OPL/ATA-Assault — "
            "leave exFAT partition and games intact"
        ),
    )
    prep_pfs.add_argument("device", type=Path, nargs="?", help="Block device path")
    prep_pfs.add_argument("--pick", type=int, metavar="N", help="Disk index from list-disks")
    prep_pfs.add_argument(
        "--cfg-dev",
        action="store_true",
        help="Create CFG-DEV instead of CFG (OPL development)",
    )
    prep_pfs.add_argument("--pfsshell", type=Path)
    prep_pfs.add_argument("--force", action="store_true")

    fin_fhdb = sub.add_parser(
        "finalize-fhdb",
        help=(
            "Após Install FHDB no PS2: FREEHDB.CNF (Manager) + ATA-Assault — "
            "antes de format-exfat"
        ),
    )
    fin_fhdb.add_argument("device", type=Path, help="Block device path")
    fin_fhdb.add_argument("--pfsshell", type=Path)
    fin_fhdb.add_argument("--force", action="store_true", required=True)

    val = sub.add_parser(
        "validate-opl-layout",
        help="Verify MBR/APAJ/exFAT layout for OPL BDM compatibility",
    )
    val.add_argument("image", type=Path)
    val.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on warnings (not only failures)",
    )
    val.add_argument(
        "--require-exfat",
        action="store_true",
        help="Fail if exFAT superblock not present in data partition",
    )

    sub.add_parser(
        "doctor",
        help="Verificar dependências no PC (pfsshell, ATA-Assault, HDD-OSD, FMCBInstaller)",
    )

    verify_dev = sub.add_parser(
        "verify-device",
        help="Checklist pós-prepare no disco (boot, FHDB, ATA-Assault, OPL)",
    )
    verify_dev.add_argument("device", type=Path)
    verify_dev.add_argument(
        "--exfat-mount",
        type=Path,
        help="Raiz exFAT montada (valida conf_opl/conf_apps e pastas)",
    )
    verify_dev.add_argument(
        "--expect-fhdb",
        action="store_true",
        help="Falhar se osdmain.elf ausente",
    )
    verify_dev.add_argument(
        "--expect-exfat",
        action="store_true",
        help="Exigir superblock exFAT formatado (layout)",
    )
    verify_dev.add_argument("--cfg-dev", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "ui":
        from .gui.main import main as gui_main

        return gui_main()

    if args.command == "build-image":
        ref = resolve_reference_mbr(args.reference_mbr)
        outcome = run_build_image(
            args.output,
            args.size_gib,
            reference_mbr=ref,
            boot_kelf=args.boot_kelf,
            init_pfs=args.init_pfs,
            format_exfat=args.format_exfat,
            volume_label=args.volume_label,
            scaffold_opl=not args.no_opl_scaffold,
            pfsshell=args.pfsshell,
        )
        for line in outcome.messages:
            stream = sys.stderr if outcome.exit_code and "Falha" in line else sys.stdout
            print(line, file=stream)
        if not args.format_exfat and not args.init_pfs:
            from .pfs_boot import pfsshell_requirements_hint
            from .exfat import format_exfat_requirements_hint

            print(
                "Tip: add --init-pfs and/or --format-exfat (Linux, root). "
                f"PFS: {pfsshell_requirements_hint()}. exFAT: {format_exfat_requirements_hint()}"
            )
            print(
                "Then install FHDB once on the PS2 (do not full-format the drive in wLE)."
            )
            print("Or run: pfs-batchkit ui")
        if outcome.exit_code == 0:
            print("Tip: pfs-batchkit validate-opl-layout", args.output)
        return outcome.exit_code

    if args.command == "init-pfs":
        code, lines = run_init_pfs(args.image, pfsshell=args.pfsshell)
        for line in lines:
            print(line, file=sys.stderr if code else sys.stdout)
        return code

    if args.command == "format-exfat":
        from .image_io import is_raw_device
        from .host.privileges import grant_destructive_write_in_process

        if is_raw_device(args.image) and not args.force:
            print(
                "format-exfat em disco físico exige --force. "
                "Só funciona após Install FHDB + ATA-Assault no disco.",
                file=sys.stderr,
            )
            return 2
        if args.force:
            grant_destructive_write_in_process()
        code, lines = run_format_exfat(
            args.image,
            size_gib=args.size_gib,
            volume_label=args.volume_label,
            scaffold_opl=not args.no_opl_scaffold,
        )
        for line in lines:
            print(line, file=sys.stderr if code else sys.stdout)
        return code

    if args.command == "scaffold-opl":
        code, lines = run_scaffold_opl(args.mount_point)
        for line in lines:
            print(line)
        return code

    if args.command == "list-disks":
        from .disks import format_disk_listing, list_physical_disks

        disks = list_physical_disks(ps2_only=args.ps2_only)
        for line in format_disk_listing(disks):
            print(line)
        return 0

    if args.command == "prepare-device":
        from .disks import format_disk_listing, list_physical_disks, resolve_disk_selection

        disks = list_physical_disks()
        device: Path | None = args.device
        if args.pick is not None:
            picked = resolve_disk_selection(str(args.pick), disks)
            if picked is None:
                print(f"Índice inválido: {args.pick}", file=sys.stderr)
                for line in format_disk_listing(disks):
                    print(line, file=sys.stderr)
                return 2
            device = picked.path
            print(f"Selecionado: {picked.summary_line()}")
        elif device is None:
            for line in format_disk_listing(disks):
                print(line)
            print(
                "Especifique o disco: prepare-device /dev/sdX --init-pfs --format-exfat --force "
                "ou --pick N",
                file=sys.stderr,
            )
            return 2

        if not args.force:
            print("prepare-device exige --force (operação destrutiva).", file=sys.stderr)
            return 2

        ref = resolve_reference_mbr(args.reference_mbr)
        outcome = run_prepare_device(
            device,
            reference_mbr=ref,
            boot_kelf=args.boot_kelf,
            init_pfs=args.init_pfs,
            format_exfat=args.format_exfat,
            volume_label=args.volume_label,
            scaffold_opl=not args.no_opl_scaffold,
            cfg_dev=args.cfg_dev,
            pfsshell=args.pfsshell,
            force=True,
            defer_exfat_format=True if args.defer_exfat else None,
        )
        for line in outcome.messages:
            stream = sys.stderr if outcome.exit_code and "Falha" in line else sys.stdout
            print(line, file=stream)
        if outcome.exit_code == 0:
            print(
                "Tip: pfs-batchkit verify-device",
                device,
                "--exfat-mount <raiz exFAT> --expect-exfat",
            )
        return outcome.exit_code

    if args.command == "recover-first-boot":
        from .image_io import wipe_exfat_region_header

        try:
            for line in wipe_exfat_region_header(args.device, force=args.force):
                print(line)
        except (ValueError, RuntimeError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    if args.command == "prepare-pfs":
        from .disks import format_disk_listing, list_physical_disks, resolve_disk_selection

        disks = list_physical_disks()
        device: Path | None = args.device
        if args.pick is not None:
            picked = resolve_disk_selection(str(args.pick), disks)
            if picked is None:
                print(f"Índice inválido: {args.pick}", file=sys.stderr)
                for line in format_disk_listing(disks):
                    print(line, file=sys.stderr)
                return 2
            device = picked.path
            print(f"Selecionado: {picked.summary_line()}")
        elif device is None:
            for line in format_disk_listing(disks):
                print(line)
            print(
                "Especifique o disco: prepare-pfs /dev/sdX --force ou --pick N",
                file=sys.stderr,
            )
            return 2

        if not args.force:
            print(
                "prepare-pfs apaga e recria __system/__sysconf (FHDB/OSD) — exige --force.",
                file=sys.stderr,
            )
            return 2

        outcome = run_prepare_pfs_device(
            device,
            cfg_dev=args.cfg_dev,
            pfsshell=args.pfsshell,
            force=True,
        )
        for line in outcome.messages:
            stream = sys.stderr if outcome.exit_code and "Falha" in line else sys.stdout
            print(line, file=stream)
        return outcome.exit_code

    if args.command == "finalize-fhdb":
        from .host.privileges import grant_destructive_write_in_process

        grant_destructive_write_in_process()
        outcome = run_finalize_fhdb_device(
            args.device,
            pfsshell=args.pfsshell,
            force=args.force,
        )
        for line in outcome.messages:
            stream = sys.stderr if outcome.exit_code and "FALHA" in line else sys.stdout
            if outcome.exit_code and ("ausente" in line or "Falha" in line):
                stream = sys.stderr
            print(line, file=stream)
        return outcome.exit_code

    if args.command == "validate-opl-layout":
        from .opl_validate import format_report, validate_opl_layout

        report = validate_opl_layout(
            args.image,
            require_exfat=args.require_exfat,
        )
        for line in format_report(report):
            stream = sys.stderr if report.failed else sys.stdout
            if "[FALHA]" in line:
                stream = sys.stderr
            elif "[AVISO]" in line:
                stream = sys.stderr
            print(line, file=stream)
        return report.exit_code(strict=args.strict)

    if args.command == "doctor":
        from .device_readiness import format_doctor_report, run_host_doctor

        report = run_host_doctor(for_prepare=True)
        for line in format_doctor_report(report):
            print(line, file=sys.stderr if not report.ok and "FALHA" in line else sys.stdout)
        if report.ok:
            print(
                "\nPróximo passo: pfs-batchkit prepare-device /dev/sdX --force --init-pfs "
                "(exFAT só depois: finalize-fhdb → format-exfat — ver specs/FHDB_OPL_BOOT.md)"
            )
        return report.exit_code

    if args.command == "verify-device":
        from .device_readiness import format_doctor_report, verify_device_for_ps2
        from .fhdb_stage import probe_fhdb_installed
        from .opl_validate import validate_opl_layout

        if args.expect_exfat:
            from .opl_validate import format_report, validate_opl_layout

            layout = validate_opl_layout(args.device, require_exfat=True)
            if layout.failed:
                for line in format_report(layout):
                    print(line, file=sys.stderr)
                return 2

        report = verify_device_for_ps2(
            args.device,
            expect_exfat_formatted=args.expect_exfat,
            expect_fhdb=args.expect_fhdb or probe_fhdb_installed(args.device),
            exfat_mount=args.exfat_mount,
            cfg_dev=args.cfg_dev,
        )
        for line in format_doctor_report(report):
            stream = sys.stdout if report.ok or "AVISO" in line else sys.stderr
            print(line, file=stream)
        return report.exit_code

    return 1


if __name__ == "__main__":
    sys.exit(main())
