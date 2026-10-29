"""Shared build/format flows for CLI and TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .boot_loader import ensure_boot_kelf, resolve_boot_kelf
from .fhdb_bdm import (
    fhdb_exfat_boot_safe,
    install_ata_assault_sysconf,
    probe_ata_assault_installed,
    resolve_defer_exfat_format,
)
from .exfat import (
    DEFAULT_VOLUME_LABEL,
    ExfatFormatError,
    format_exfat_region,
    format_exfat_requirements_hint,
)
from .image_io import (
    build_and_save,
    device_size_bytes,
    is_raw_device,
    write_boot_region_to_device,
)
from .layout import HybridLayout, plan_layout, plan_layout_placeholder
from .opl import write_opl_tree
from .pfs_boot import (
    PfsInitError,
    init_boot_pfs_partitions,
    pfsshell_requirements_hint,
)


def resolve_reference_mbr(reference_mbr: Path | None) -> Path | None:
    if reference_mbr is not None and reference_mbr.is_file():
        return reference_mbr
    default_ref = Path("/tmp/pfs-batchkit/mbr.img")
    if default_ref.is_file():
        return default_ref
    return reference_mbr


def ensure_reference_mbr(path: Path) -> None:
    """Download PFS-BatchKit mbr.img if missing."""
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request

    url = (
        "https://raw.githubusercontent.com/GDX-X/PFS-BatchKit-Manager/"
        "main/PFS-BatchKit-Manager/BAT/mbr.img"
    )
    urllib.request.urlretrieve(url, path)


@dataclass
class BuildImageOutcome:
    layout: HybridLayout
    messages: list[str] = field(default_factory=list)
    exit_code: int = 0
    opl_mount: Path | None = None


def run_build_image(
    output: Path,
    size_gib: float,
    *,
    reference_mbr: Path | None = None,
    boot_kelf: Path | None = None,
    init_pfs: bool = False,
    format_exfat: bool = False,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    scaffold_opl: bool = True,
    pfsshell: Path | None = None,
) -> BuildImageOutcome:
    messages: list[str] = []
    exit_code = 0
    ref = resolve_reference_mbr(reference_mbr)
    kelf_path = resolve_boot_kelf(boot_kelf)
    if kelf_path is not None:
        messages.extend(ensure_boot_kelf(kelf_path))
    layout = build_and_save(
        output,
        size_gib,
        reference_mbr=ref,
        boot_kelf=kelf_path,
    )
    messages.append(f"Imagem gravada: {output}")
    messages.append(
        f"APA boot: setores 0–{layout.boot_end_sector} "
        f"({layout.boot_end_sector * 512 // (1024**2)} MiB)"
    )
    exfat_gib = layout.exfat_sector_count * 512 / (1024**3)
    messages.append(
        f"exFAT: setor {layout.exfat_start_sector} até o fim do disco "
        f"({layout.exfat_sector_count} setores, {exfat_gib:.2f} GiB)"
    )

    if init_pfs:
        try:
            pfs_result = init_boot_pfs_partitions(output, pfsshell=pfsshell)
            messages.append(
                f"PFS OK em {', '.join(pfs_result.partitions)} "
                f"({pfs_result.pfsshell})"
            )
        except PfsInitError as exc:
            messages.append(f"Falha PFS: {exc}")
            messages.append(f"Dica: {pfsshell_requirements_hint()}")
            exit_code = 2

    if format_exfat:
        try:
            result = format_exfat_region(
                output,
                layout,
                volume_label=volume_label,
                scaffold_opl=scaffold_opl,
            )
            messages.append(
                f"exFAT formatado label={result.volume_label!r} "
                f"({result.byte_size} bytes)"
            )
            if result.mount_point:
                messages.append(f"Pastas OPL criadas (mount {result.mount_point})")
        except ExfatFormatError as exc:
            messages.append(f"Falha exFAT: {exc}")
            messages.append(f"Dica: {format_exfat_requirements_hint()}")
            exit_code = 2

    return BuildImageOutcome(layout=layout, messages=messages, exit_code=exit_code)


def run_init_pfs(image: Path, *, pfsshell: Path | None = None) -> tuple[int, list[str]]:
    try:
        result = init_boot_pfs_partitions(image, pfsshell=pfsshell)
    except PfsInitError as exc:
        return 2, [f"Falha PFS: {exc}", pfsshell_requirements_hint()]
    return 0, [f"PFS OK em {', '.join(result.partitions)}"]


def run_format_exfat(
    image: Path,
    *,
    size_gib: float | None = None,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    scaffold_opl: bool = True,
) -> tuple[int, list[str]]:
    if is_raw_device(image):
        size_bytes = device_size_bytes(image)
    else:
        size_bytes = image.stat().st_size
    if size_gib is not None:
        size_bytes = int(size_gib * (1024**3)) // 512 * 512
    layout = plan_layout(size_bytes)
    try:
        result = format_exfat_region(
            image,
            layout,
            volume_label=volume_label,
            scaffold_opl=scaffold_opl,
        )
    except ExfatFormatError as exc:
        return 2, [f"Falha exFAT: {exc}", format_exfat_requirements_hint()]
    lines = [f"exFAT OK em {image} label={result.volume_label!r}"]
    if result.mount_point:
        lines.append(f"Pastas OPL em mount temporário {result.mount_point}")
    return 0, lines


def run_scaffold_opl(mount_point: Path, *, cfg_dev: bool = False) -> tuple[int, list[str]]:
    result = write_opl_tree(mount_point, cfg_dev=cfg_dev)
    return 0, [
        f"Pastas OPL criadas em {mount_point}",
        f"Diretórios: {', '.join(result.created_dirs)}",
        f"Guia: {result.readme_path}",
    ]


def _reject_system_disk(device: Path) -> tuple[int, list[str]] | None:
    from .disks import is_likely_system_disk, list_physical_disks

    if not is_likely_system_disk(device):
        return None
    for d in list_physical_disks():
        if d.path == device:
            line = d.summary_line()
            break
    else:
        line = str(device)
    return 2, [
        "Recusado: este dispositivo é o disco do sistema Linux (ex. /dev/sda).",
        "Ligue o HDD PS2 por USB/SATA e escolha outro dispositivo (ex. /dev/sdb).",
        line,
    ]


def _validate_hybrid_layout_size(
    device: Path,
    *,
    known_size_bytes: int | None,
    sudo_password: str | None,
) -> str | None:
    """Return user-facing error, or None if size OK / validated later as root."""
    from .host.runner import is_admin

    if known_size_bytes and known_size_bytes > 0:
        try:
            plan_layout(known_size_bytes)
        except ValueError as exc:
            return str(exc)
        return None

    if sudo_password and not is_admin():
        return None

    if not is_admin():
        return (
            f"Sem permissão para ler {device}. Informe a senha sudo nesta etapa "
            "ou execute: sudo pfs-batchkit-ui"
        )

    try:
        plan_layout(device_size_bytes(device))
    except (ValueError, OSError) as exc:
        return str(exc)
    return None


def run_prepare_device(
    device: Path,
    *,
    reference_mbr: Path | None = None,
    boot_kelf: Path | None = None,
    init_pfs: bool = False,
    format_exfat: bool = False,
    volume_label: str = DEFAULT_VOLUME_LABEL,
    scaffold_opl: bool = True,
    pfsshell: Path | None = None,
    force: bool = False,
    sudo_password: str | None = None,
    cfg_dev: bool = False,
    defer_exfat_format: bool | None = None,
    pfs_only: bool = False,
    known_size_bytes: int | None = None,
) -> BuildImageOutcome:
    """Prepare hybrid layout in-place on a physical disk (real size, no .img step).

    ``pfs_only``: reformata só PFS (__system / __sysconf), injecta FHDB/OSD/OPL/ATA-Assault;
    não regrava a região boot __mbr nem formata exFAT (jogos intactos).
    """
    if pfs_only:
        init_pfs = True
        format_exfat = False
        defer_exfat_format = True
    messages: list[str] = []
    exit_code = 0
    defer_exfat = resolve_defer_exfat_format(defer_exfat_format)
    opl_mount: Path | None = None
    blocked = _reject_system_disk(device)
    if blocked is not None:
        return BuildImageOutcome(
            layout=plan_layout_placeholder(),
            messages=blocked[1],
            exit_code=blocked[0],
        )

    from .host.privileges import invoke_cli_elevated
    from .host.runner import is_admin

    if not pfs_only:
        size_err = _validate_hybrid_layout_size(
            device,
            known_size_bytes=known_size_bytes,
            sudo_password=sudo_password,
        )
        if size_err:
            return BuildImageOutcome(
                layout=plan_layout_placeholder(),
                messages=[f"Disco inválido para layout híbrido: {size_err}"],
                exit_code=2,
            )

    if sudo_password and not is_admin():
        ref = resolve_reference_mbr(reference_mbr)
        cmd = "prepare-pfs" if pfs_only else "prepare-device"
        cli_args = [cmd, str(device), "--force"]
        if not pfs_only:
            if ref is not None:
                cli_args.extend(["--reference-mbr", str(ref)])
            if boot_kelf is not None:
                cli_args.extend(["--boot-kelf", str(boot_kelf)])
            else:
                kelf = resolve_boot_kelf(None)
                if kelf is not None:
                    cli_args.extend(["--boot-kelf", str(kelf)])
            if init_pfs:
                cli_args.append("--init-pfs")
            if format_exfat:
                cli_args.append("--format-exfat")
            if not scaffold_opl:
                cli_args.append("--no-opl-scaffold")
            defer = resolve_defer_exfat_format(defer_exfat_format)
            if defer:
                cli_args.append("--defer-exfat")
            if volume_label != DEFAULT_VOLUME_LABEL:
                cli_args.extend(["--volume-label", volume_label])
        if cfg_dev:
            cli_args.append("--cfg-dev")
        if pfsshell is not None:
            cli_args.extend(["--pfsshell", str(pfsshell)])
        proc = invoke_cli_elevated(cli_args, password=sudo_password)
        out_lines = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()]
        if proc.returncode != 0:
            if not out_lines:
                out_lines = [f"sudo/prepare-device falhou (código {proc.returncode})"]
            return BuildImageOutcome(
                layout=plan_layout_placeholder(),
                messages=out_lines,
                exit_code=2 if proc.returncode != 0 else 0,
            )
        try:
            layout = plan_layout(device_size_bytes(device))
        except (ValueError, OSError):
            layout = plan_layout_placeholder()
        from .opl_mount import parse_opl_mount_message

        opl_mount: Path | None = None
        for ln in out_lines:
            parsed = parse_opl_mount_message(ln)
            if parsed is not None:
                opl_mount = parsed
        return BuildImageOutcome(
            layout=layout,
            messages=out_lines or ["Preparar disco: OK."],
            exit_code=0,
            opl_mount=opl_mount,
        )

    if init_pfs or format_exfat:
        from .device_readiness import format_doctor_report, run_host_doctor

        host_doc = run_host_doctor(for_prepare=True)
        messages.append("--- Dependências (PC) ---")
        messages.extend(format_doctor_report(host_doc))
        if not host_doc.ok:
            return BuildImageOutcome(
                layout=plan_layout_placeholder(),
                messages=messages,
                exit_code=2,
            )

    ref_path = resolve_reference_mbr(reference_mbr) or Path("/tmp/pfs-batchkit/mbr.img")
    if pfs_only:
        try:
            layout = plan_layout(device_size_bytes(device))
        except (ValueError, OSError) as exc:
            return BuildImageOutcome(
                layout=plan_layout_placeholder(),
                messages=[f"Não foi possível ler tamanho do disco: {exc}"],
                exit_code=2,
            )
        messages.append(
            "Modo só PFS: __mbr/boot e partição exFAT (jogos ISO) permanecem intactos."
        )
        messages.append(
            "Serão recriados __system / __sysconf (mkfs) e injectados FHDB/OSD, "
            "OPL em PFS e drivers ATA-Assault."
        )
        total_gib = layout.total_bytes / (1024**3)
        messages.append(f"Disco: {device} ({total_gib:.2f} GiB totais)")
    else:
        try:
            ensure_reference_mbr(ref_path)
        except OSError as exc:
            try:
                fallback_size = device_size_bytes(device)
            except (ValueError, OSError):
                return BuildImageOutcome(
                    layout=plan_layout_placeholder(),
                    messages=[f"Não foi possível obter mbr.img (boot FHDB): {exc}"],
                    exit_code=2,
                )
            return BuildImageOutcome(
                layout=plan_layout(fallback_size),
                messages=[f"Não foi possível obter mbr.img (boot FHDB): {exc}"],
                exit_code=2,
            )
        ref = ref_path

        kelf_path = resolve_boot_kelf(boot_kelf)
        if kelf_path is not None:
            try:
                messages.extend(ensure_boot_kelf(kelf_path))
            except OSError as exc:
                try:
                    fallback_size = device_size_bytes(device)
                except (ValueError, OSError):
                    return BuildImageOutcome(
                        layout=plan_layout_placeholder(),
                        messages=[f"Não foi possível preparar boot KELF wLaunchELF: {exc}"],
                        exit_code=2,
                    )
                return BuildImageOutcome(
                    layout=plan_layout(fallback_size),
                    messages=[f"Não foi possível preparar boot KELF wLaunchELF: {exc}"],
                    exit_code=2,
                )

        try:
            layout = write_boot_region_to_device(
                device,
                reference_mbr=ref,
                boot_kelf=kelf_path,
                force=force,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            try:
                fallback_size = device_size_bytes(device)
            except (ValueError, OSError):
                return BuildImageOutcome(
                    layout=plan_layout_placeholder(),
                    messages=[str(exc)],
                    exit_code=2,
                )
            return BuildImageOutcome(
                layout=plan_layout(fallback_size),
                messages=[str(exc)],
                exit_code=2,
            )

        total_gib = layout.total_bytes / (1024**3)
        messages.append(f"Disco preparado in-place: {device} ({total_gib:.2f} GiB totais)")
        messages.append(
            f"APA boot: setores 0–{layout.boot_end_sector} "
            f"({layout.boot_end_sector * 512 // (1024**2)} MiB)"
        )
        exfat_gib = layout.exfat_sector_count * 512 / (1024**3)
        messages.append(
            f"exFAT (partição MBR): setor {layout.exfat_start_sector} até o fim "
            f"({layout.exfat_sector_count} setores, {exfat_gib:.2f} GiB)"
        )

    if init_pfs:
        try:
            pfs_result = init_boot_pfs_partitions(device, pfsshell=pfsshell)
            messages.append(
                f"PFS OK em {', '.join(pfs_result.partitions)} "
                f"({pfs_result.pfsshell})"
            )
        except PfsInitError as exc:
            messages.append(f"Falha PFS: {exc}")
            messages.append(f"Dica: {pfsshell_requirements_hint()}")
            exit_code = 2

    if init_pfs and exit_code == 0:
        from .pfs_boot import verify_pfs_partitions_mounted

        pfs_ok, pfs_lines = verify_pfs_partitions_mounted(device, pfsshell=pfsshell)
        messages.extend(pfs_lines)
        if not pfs_ok:
            exit_code = 2

    if init_pfs and exit_code == 0:
        import os

        from .fhdb_stage import (
            fhdb_payload_dir,
            install_fhdb_payload_to_system,
            install_manager_hdd_osd,
            probe_fhdb_installed,
        )

        try:
            if os.environ.get("PFS_BATCHKIT_FHDB_PAYLOAD"):
                payload_result = install_fhdb_payload_to_system(device)
                messages.extend(payload_result.messages)
            else:
                osd_result = install_manager_hdd_osd(device)
                messages.extend(osd_result.messages)
        except PfsInitError as exc:
            messages.append(str(exc))
            exit_code = 2

        if exit_code == 0:
            try:
                from .pfs_opl_config import install_opl_pfs_config

                pfs_opl = install_opl_pfs_config(device, pfsshell=pfsshell)
                messages.extend(pfs_opl.messages)
            except PfsInitError as exc:
                messages.append(str(exc))
                exit_code = 2

        if exit_code == 0 and not probe_fhdb_installed(device):
            messages.append(
                "FHDB: osdmain.elf ainda ausente — no Manager, copie Browser/FHDB para "
                "HDD-OSD/__system e repita, ou use FMCBInstaller no PS2 (mass:/APPS/FreeMcBoot)."
            )

        if exit_code == 0:
            try:
                bdm_result = install_ata_assault_sysconf(device)
                messages.extend(bdm_result.messages)
            except PfsInitError as exc:
                messages.append(str(exc))
                exit_code = 2

    if format_exfat and exit_code == 0 and not defer_exfat:
        from .fhdb_stage import probe_fhdb_installed

        fhdb_ok = probe_fhdb_installed(device)
        ata_ok = probe_ata_assault_installed(device)
        safe, boot_msg = fhdb_exfat_boot_safe(
            fhdb_installed=fhdb_ok,
            ata_assault_installed=ata_ok,
            format_exfat=True,
            defer_exfat=False,
        )
        if not safe and boot_msg:
            defer_exfat = True
            messages.append(boot_msg)

    exfat_formatted = False
    if format_exfat and exit_code == 0:
        if defer_exfat:
            messages.append(
                "exFAT: format. adiado (partição MBR já reservada). "
                "FreeHDBoot trava se o volume exFAT estiver formatado antes do menu FHDB — "
                "instale FHDB no PS2, reinicie, depois: "
                "pfs-batchkit format-exfat DISCO ou desmarque «Adiar exFAT» e repita o prepare "
                "(com drivers ATA-Assault já em __sysconf)."
            )
        else:
            try:
                from .host.detect import host_os
                from .opl_mount import opl_mount_message, persistent_opl_mount_path

                keep_at: Path | None = None
                if scaffold_opl and host_os() == "linux":
                    keep_at = persistent_opl_mount_path(volume_label)

                result = format_exfat_region(
                    device,
                    layout,
                    volume_label=volume_label,
                    scaffold_opl=scaffold_opl,
                    cfg_dev=cfg_dev,
                    keep_mounted_at=keep_at,
                )
                exfat_formatted = True
                messages.append(
                    f"exFAT formatado label={result.volume_label!r} "
                    f"({result.byte_size} bytes)"
                )
                if scaffold_opl:
                    from .opl import OPL_DIR_NAMES, opl_cfg_dir_name

                    names = ", ".join(
                        list(OPL_DIR_NAMES) + [opl_cfg_dir_name(cfg_dev=cfg_dev)]
                    )
                    messages.append(f"Biblioteca OPL criada (raiz exFAT): {names}")
                    messages.append(
                        "OPL Manager V24: defina OPL_FOLDER para a raiz do volume montado "
                        "(CD/, DVD/, ART/ obrigatórios para escanear)."
                    )
                if result.mount_persisted and result.mount_point:
                    opl_mount = Path(result.mount_point)
                    messages.append(
                        f"Partição exFAT do disco físico montada em {opl_mount} "
                        f"(losetup na região híbrida — não é um .img separado) — "
                        f"pronto para copiar jogos."
                    )
                    messages.append(opl_mount_message(opl_mount))
                elif result.mount_point:
                    messages.append(
                        f"Pastas OPL criadas (mount temporário {result.mount_point})"
                    )
            except ExfatFormatError as exc:
                messages.append(f"Falha exFAT: {exc}")
                messages.append(f"Dica: {format_exfat_requirements_hint()}")
                exit_code = 2

    if exit_code == 0:
        from .boot_ready import verify_boot_ready
        from .opl_validate import format_report, validate_opl_layout

        boot = verify_boot_ready(device)
        messages.extend(boot.messages)
        if not boot.ok and not pfs_only:
            exit_code = 2

        messages.append("--- Validação layout OPL ---")
        layout_report = validate_opl_layout(
            device,
            require_exfat=format_exfat and not defer_exfat and not pfs_only,
        )
        messages.extend(format_report(layout_report))
        if layout_report.failed:
            exit_code = 2

        if exit_code == 0 and exfat_formatted:
            from .fhdb_stage import probe_fhdb_installed

            if probe_fhdb_installed(device) and not probe_ata_assault_installed(device):
                messages.append(
                    "AVISO BOOT PS2: FreeHDBoot (osdmain.elf) + exFAT no mesmo disco sem "
                    "ATA-Assault em __sysconf/FMCB/ → tela preta ao ligar. "
                    "Reprepare com ATA-Assault OK ou repita prepare com --defer-exfat, "
                    "boot FHDB no PS2, depois format-exfat."
                )
                exit_code = 2

        if exit_code == 0:
            if pfs_only:
                tail = (
                    "PFS atualizado: __system/__sysconf + FHDB/OSD + OPL (PFS) + ATA-Assault. "
                    "exFAT e ISOs não foram alterados."
                )
            else:
                tail = (
                    "Pronto no PC (BatchKit APA-Jail): boot __mbr + PFS __system/__sysconf"
                )
                if exfat_formatted:
                    tail += " + exFAT OPL formatado."
                elif format_exfat and defer_exfat:
                    tail += "; exFAT pendente após FHDB no PS2."
                else:
                    tail += "."
            messages.append(tail)
            if not pfs_only:
                messages.append(
                    "PS2: se o Manager já tinha HDD-OSD/__system no PC, o prepare injecta FHDB "
                    "como «Install HDD-OSD»; senão use FMCBInstaller uma vez (mass:/APPS/FreeMcBoot)."
                )
            else:
                messages.append(
                    "PS2: reinicie após a actualização — menu OSD/FHDB vem de __system; "
                    "jogos OPL continuam na raiz exFAT montada (CD/, DVD/, …)."
                )

        from .device_readiness import format_doctor_report, verify_device_for_ps2

        fhdb_now = probe_fhdb_installed(device) if init_pfs else False
        dev_report = verify_device_for_ps2(
            device,
            expect_exfat_formatted=exfat_formatted,
            expect_fhdb=fhdb_now,
            exfat_mount=opl_mount,
            cfg_dev=cfg_dev,
        )
        messages.append("--- Verificação dispositivo (PS2) ---")
        messages.extend(format_doctor_report(dev_report))
        if not dev_report.ok:
            exit_code = 2

    return BuildImageOutcome(
        layout=layout,
        messages=messages,
        exit_code=exit_code,
        opl_mount=opl_mount,
    )


def run_prepare_pfs_device(
    device: Path,
    *,
    reference_mbr: Path | None = None,
    pfsshell: Path | None = None,
    force: bool = False,
    sudo_password: str | None = None,
    cfg_dev: bool = False,
) -> BuildImageOutcome:
    """Atualizar só PFS (FHDB/OSD/OPL/ATA-Assault) — exFAT intacto."""
    return run_prepare_device(
        device,
        reference_mbr=reference_mbr,
        boot_kelf=None,
        init_pfs=True,
        format_exfat=False,
        scaffold_opl=False,
        pfsshell=pfsshell,
        force=force,
        sudo_password=sudo_password,
        cfg_dev=cfg_dev,
        defer_exfat_format=True,
        pfs_only=True,
    )


def requirements_lines() -> list[str]:
    from .host.detect import host_os

    return [
        f"Plataforma detectada: {host_os()}",
        f"PFS: {pfsshell_requirements_hint()}",
        f"exFAT: {format_exfat_requirements_hint()}",
        "Gravar disco: confirme na UI ou use --force; root/admin dispensa PFS_BATCHKIT_ALLOW_WRITE",
        "Linux sem root: informe senha sudo na tela ou rode sudo ./pfs-batchkit-ui",
        "Linux/macOS: sudo ou root; Windows: terminal Administrador",
        "FHDB + OPL: specs/FHDB_OPL_BOOT.md — mbr.img + init-pfs + exFAT; FMCBInstaller no PS2 (ou env)",
        "Actualizar FHDB/OSD sem apagar jogos: prepare-pfs ou menu «Atualizar só PFS» na UI",
        "Detalhes: specs/CROSS_PLATFORM.md",
    ]
