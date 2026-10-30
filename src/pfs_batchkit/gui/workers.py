"""Background workers for long-running disk operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..host.privileges import grant_destructive_write_in_process
from ..host.runner import is_admin
from ..opl_validate import format_report, validate_opl_layout
from ..opl_mount import parse_opl_mount_message
from ..workflows import (
    ensure_reference_mbr,
    resolve_reference_mbr,
    run_build_image,
    run_finalize_fhdb_device,
    run_prepare_device,
    run_scaffold_opl,
)
from .state import WizardMode, WizardState


class PrepareDiskWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        state = self._state
        if state.selected_disk is None:
            self.line.emit("Nenhum disco selecionado.")
            self.finished_with_code.emit(2)
            return

        grant_destructive_write_in_process()
        sudo_pw = state.sudo_password.strip() or None
        if not is_admin() and not sudo_pw:
            self.line.emit(
                "Informe a senha sudo na etapa anterior ou execute o app como root."
            )
            self.finished_with_code.emit(2)
            return

        try:
            ensure_reference_mbr(state.reference_mbr)
        except OSError as exc:
            self.line.emit(f"Não foi possível obter mbr.img: {exc}")
            self.finished_with_code.emit(2)
            return

        self.line.emit(f"Preparando {state.selected_disk.path} …")
        if state.mode == WizardMode.PREPARE_PFS:
            self.line.emit(
                "Modo só PFS: exFAT/jogos intactos — mkfs __system/__sysconf + FHDB/OSD/OPL/ATA-Assault."
            )
        try:
            outcome = run_prepare_device(
                state.selected_disk.path,
                reference_mbr=state.reference_mbr,
                init_pfs=state.init_pfs,
                format_exfat=state.format_exfat,
                scaffold_opl=state.scaffold_opl,
                cfg_dev=state.cfg_dev,
                force=True,
                sudo_password=sudo_pw,
                defer_exfat_format=state.defer_exfat_format,
                pfs_only=state.mode == WizardMode.PREPARE_PFS,
                known_size_bytes=(
                    state.selected_disk.size_bytes
                    if state.selected_disk.size_bytes > 0
                    else None
                ),
            )
        except Exception as exc:
            self.line.emit(f"Erro inesperado ao preparar disco: {exc}")
            self.finished_with_code.emit(2)
            return
        for msg in outcome.messages:
            self.line.emit(msg)
            parsed = parse_opl_mount_message(msg)
            if parsed is not None:
                state.opl_root = parsed
        if outcome.opl_mount is not None:
            state.opl_root = outcome.opl_mount
        self.finished_with_code.emit(outcome.exit_code)


class FinalizeFhdbWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        state = self._state
        if state.selected_disk is None:
            self.line.emit("Nenhum disco selecionado.")
            self.finished_with_code.emit(2)
            return

        grant_destructive_write_in_process()
        sudo_pw = state.sudo_password.strip() or None
        if not is_admin() and not sudo_pw:
            self.line.emit(
                "Informe a senha sudo na etapa anterior ou execute o app como root."
            )
            self.finished_with_code.emit(2)
            return

        self.line.emit(
            f"Finalizando FHDB em {state.selected_disk.path} "
            "(FREEHDB.CNF + ATA-Assault) …"
        )
        try:
            outcome = run_finalize_fhdb_device(
                state.selected_disk.path,
                force=True,
                sudo_password=sudo_pw,
            )
        except Exception as exc:
            self.line.emit(f"Erro inesperado: {exc}")
            self.finished_with_code.emit(2)
            return
        for msg in outcome.messages:
            self.line.emit(msg)
        self.finished_with_code.emit(outcome.exit_code)


class GamesCopyWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        from .opl_transfer import copy_games_to_opl_library

        opl_root = self._state.opl_root.expanduser()
        source = self._state.games_source_dir.expanduser()
        medium = self._state.games_medium
        med_arg = None if medium == "auto" else medium.upper()
        self.line.emit(f"Origem: {source}")
        self.line.emit(f"Destino OPL: {opl_root}")
        try:
            code, lines = copy_games_to_opl_library(
                opl_root,
                source,
                medium=med_arg,
            )
        except OSError as exc:
            self.line.emit(str(exc))
            self.finished_with_code.emit(2)
            return
        for ln in lines:
            self.line.emit(ln)
        self.finished_with_code.emit(code)


class ValidateLayoutWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        image = self._state.image_path.expanduser()
        if not image.is_file():
            self.line.emit(f"Imagem não encontrada: {image}")
            self.finished_with_code.emit(2)
            return
        self.line.emit(f"Validando {image} …")
        report = validate_opl_layout(
            image,
            require_exfat=self._state.validate_require_exfat,
        )
        for line in format_report(report):
            self.line.emit(line)
        code = report.exit_code(strict=self._state.validate_strict)
        self.finished_with_code.emit(code)


class BuildImageWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        ref = resolve_reference_mbr(self._state.reference_mbr)
        try:
            ensure_reference_mbr(ref if ref else Path("/tmp/pfs-batchkit/mbr.img"))
        except OSError as exc:
            self.line.emit(f"mbr.img: {exc}")
            self.finished_with_code.emit(2)
            return
        self.line.emit(
            f"Criando imagem {self._state.build_output} "
            f"({self._state.build_size_gib} GiB) …"
        )
        outcome = run_build_image(
            self._state.build_output,
            self._state.build_size_gib,
            reference_mbr=ref,
            init_pfs=self._state.build_init_pfs,
            format_exfat=self._state.build_format_exfat,
            scaffold_opl=self._state.build_format_exfat,
        )
        for msg in outcome.messages:
            self.line.emit(msg)
        self.finished_with_code.emit(outcome.exit_code)


class ScaffoldOplWorker(QThread):
    line = Signal(str)
    finished_with_code = Signal(int)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def run(self) -> None:
        from ..opl_mount import resolve_scaffold_mount

        mount, hints = resolve_scaffold_mount(
            self._state.scaffold_mount,
            disk=self._state.selected_disk,
        )
        for hint in hints:
            self.line.emit(hint)
        if mount is None:
            self.finished_with_code.emit(2)
            return
        self._state.scaffold_mount = mount
        code, lines = run_scaffold_opl(mount, cfg_dev=self._state.cfg_dev)
        for line in lines:
            self.line.emit(line)
        self.finished_with_code.emit(code)
