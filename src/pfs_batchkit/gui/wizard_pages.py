"""Qt wizard pages (multi-flow)."""

from __future__ import annotations

from pathlib import Path
from typing import Type

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from .. import __version__
from ..disks import PhysicalDisk, list_physical_disks
from ..host.detect import host_os
from ..host.privileges import effective_user_home, elevation_hint_short
from ..host.runner import is_admin
from ..workflows import requirements_lines
from ..opl_mount import (
    discover_exfat_volume_root,
    discover_opl_root,
    resolve_scaffold_mount,
    suggest_opl_root_path,
)
from .page_ids import PageId
from .state import AdvancedAction, WizardMode, WizardState
from .workers import (
    BuildImageWorker,
    PrepareDiskWorker,
    ScaffoldOplWorker,
    ValidateLayoutWorker,
)


def _add_sudo_row(form: QFormLayout) -> QLineEdit | None:
    if not is_admin() and host_os() != "windows":
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText("se necessário")
        form.addRow("Senha sudo:", field)
        return field
    return None


def _default_image_path_for_ui(path: Path) -> Path:
    """Avoid /root/ps2-hdd.img when the app runs under sudo."""
    path = path.expanduser()
    user_home = effective_user_home()
    if path.is_file():
        return path
    if path.parent == Path.home() and user_home != Path.home():
        return user_home / path.name
    alt = user_home / path.name
    if alt.is_file():
        return alt
    return path


def _image_missing_message(path: Path) -> str:
    suggested = _default_image_path_for_ui(path)
    extra = f"\n\nSugestão: {suggested}" if suggested != path.expanduser() else ""
    return f"Arquivo não encontrado:\n{path}{extra}"


class BatchKitWizardPage(QWizardPage):
    """QWizardPage with numeric id for QWizard.setPage()."""

    def __init__(self, page_id: PageId) -> None:
        super().__init__()
        self._page_id = int(page_id)

    def pageId(self) -> int:  # noqa: N802 (Qt API name)
        return self._page_id


class WelcomePage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.WELCOME)
        self._state = state
        self.setTitle("Bem-vindo")
        self.setSubTitle("Escolha o que deseja fazer neste assistente.")

        layout = QVBoxLayout(self)
        self._mode = QComboBox()
        self._mode.addItem("Preparar HDD PS2 no disco físico (recomendado)", WizardMode.PREPARE_DISK)
        self._mode.addItem(
            "Atualizar só PFS (FHDB/OSD/OPL) — manter exFAT/jogos",
            WizardMode.PREPARE_PFS,
        )
        self._mode.addItem("Validar layout OPL de uma imagem .img", WizardMode.VALIDATE_LAYOUT)
        self._mode.addItem("Modo avançado (criar .img, pastas OPL, …)", WizardMode.ADVANCED)
        layout.addWidget(QLabel("Tarefa:"))
        layout.addWidget(self._mode)

        req_box = QGroupBox("Requisitos")
        req_layout = QVBoxLayout(req_box)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        req_text = QTextEdit()
        req_text.setReadOnly(True)
        req_text.setFont(mono)
        req_text.setPlainText("\n".join(requirements_lines()))
        req_text.setMaximumHeight(140)
        req_layout.addWidget(req_text)
        layout.addWidget(req_box)
        layout.addWidget(QLabel(f"<i>{elevation_hint_short()}</i>"))

    def nextId(self) -> int:
        mode = self._mode.currentData()
        self._state.mode = WizardMode(mode)
        self._state.log_lines.clear()
        if self._state.mode == WizardMode.PREPARE_DISK:
            return int(PageId.DISK)
        if self._state.mode == WizardMode.PREPARE_PFS:
            return int(PageId.DISK)
        if self._state.mode == WizardMode.VALIDATE_LAYOUT:
            return int(PageId.VALIDATE_INPUT)
        return int(PageId.ADVANCED)


class DiskSelectPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.DISK)
        self._state = state
        self.setTitle("Escolher disco")
        self.setSubTitle("Confira modelo e tamanho antes de continuar.")

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        refresh = QPushButton("Atualizar lista")
        refresh.clicked.connect(self._refresh_disks)
        row.addWidget(refresh)
        row.addStretch()
        layout.addLayout(row)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection)
        layout.addWidget(self._list)
        self._detail = QLabel("Nenhum disco selecionado.")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        form = QFormLayout()
        self._manual = QLineEdit()
        self._manual.setPlaceholderText("/dev/sdb")
        self._manual.textChanged.connect(self._on_manual)
        form.addRow("Caminho manual:", self._manual)
        layout.addLayout(form)

        self._warn = QCheckBox("Confirmo apagar/gravar neste disco (não é o disco do sistema)")
        self._warn.stateChanged.connect(lambda _state: self.completeChanged.emit())
        layout.addWidget(self._warn)
        self._disks: list[PhysicalDisk] = []

    def initializePage(self) -> None:
        self.setSubTitle("HDD PS2 — operação destrutiva.")
        self._refresh_disks()

    def nextId(self) -> int:
        return int(PageId.PREPARE_OPTIONS)

    def _refresh_disks(self) -> None:
        self._list.clear()
        self._disks = list_physical_disks()
        for d in self._disks:
            item = QListWidgetItem(d.summary_line())
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _on_selection(self, current: QListWidgetItem | None, _prev) -> None:
        if not current:
            return
        disk: PhysicalDisk = current.data(Qt.ItemDataRole.UserRole)
        self._state.selected_disk = disk
        self._manual.blockSignals(True)
        self._manual.setText(str(disk.path))
        self._manual.blockSignals(False)
        self._detail.setText(disk.summary_line())
        self.completeChanged.emit()

    def _on_manual(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        path = Path(text)
        for d in self._disks:
            if d.path == path:
                self._state.selected_disk = d
                self._detail.setText(d.summary_line())
                self.completeChanged.emit()
                return
        self._state.selected_disk = PhysicalDisk(
            index=-1,
            path=path,
            model="(manual)",
            size_bytes=0,
            bus="",
            ps2_hdd=False,
            hdl_path="",
            mountpoints=(),
            notes="",
        )
        self._detail.setText(str(path))
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._state.selected_disk is not None and self._warn.isChecked()


class PrepareOptionsPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.PREPARE_OPTIONS)
        self._state = state
        self.setTitle("Opções de preparo")
        self.setSubTitle("PFS + exFAT + pastas OPL na raiz do volume.")

        layout = QVBoxLayout(self)
        self._init_pfs = QCheckBox("Inicializar PFS (__system, __sysconf)")
        self._init_pfs.setChecked(True)
        self._format_exfat = QCheckBox("Formatar exFAT + biblioteca OPL (CD/, DVD/, APPS/, …)")
        self._format_exfat.setChecked(True)
        self._cfg_dev = QCheckBox("CFG-DEV em vez de CFG")
        layout.addWidget(self._init_pfs)
        layout.addWidget(self._format_exfat)
        layout.addWidget(self._cfg_dev)
        self._pfs_only_hint = QLabel()
        self._pfs_only_hint.setWordWrap(True)
        self._pfs_only_hint.setVisible(False)
        layout.addWidget(self._pfs_only_hint)

        layout.addWidget(
            QLabel(
                "<small><b>Tela preta no PS2?</b> FreeHDBoot + exFAT formatado no mesmo HDD "
                "trava sem drivers ATA-Assault em __sysconf. O prepare injecta ATA-Assault "
                "antes do exFAT; se tiver <code>HDD-OSD/__system</code> (osdmain.elf), "
                "confira no log «ATA-Assault» OK. Disco já gravado: reprepare com "
                "<code>PFS_BATCHKIT_DEFER_EXFAT=1</code> ou veja specs/FHDB_OPL_BOOT.md.</small>"
            )
        )
        layout.addWidget(
            QLabel(
                "<small><b>Menu OSD (Manager):</b> no PC, o Manager injecta "
                "&laquo;Install HDD-OSD&raquo; a partir de <code>HDD-OSD/__system</code> no clone — "
                "o PFS BatchKit faz o mesmo se essa pasta existir. "
                "Inicializar PFS apaga FHDB já gravado no disco.</small>"
            )
        )

        form = QFormLayout()
        self._mbr = QLineEdit(str(state.reference_mbr))
        form.addRow("mbr.img:", self._mbr)
        self._sudo = _add_sudo_row(form)
        layout.addLayout(form)

    def initializePage(self) -> None:
        pfs_only = self._state.mode == WizardMode.PREPARE_PFS
        self._pfs_only_hint.setVisible(pfs_only)
        self._format_exfat.setVisible(not pfs_only)
        if pfs_only:
            self.setTitle("Atualizar PFS (FHDB / menu OSD / OPL)")
            self.setSubTitle(
                "Recria __system e __sysconf no PC — exFAT e ISOs na partição de jogos ficam intactos."
            )
            self._pfs_only_hint.setText(
                "Equivalente a «Install HDD-OSD» no Manager + drivers ATA-Assault. "
                "Requer pasta HDD-OSD/__system do clone Manager (osdmain.elf) ou "
                "PFS_BATCHKIT_FHDB_PAYLOAD."
            )
            self._init_pfs.setChecked(True)
            self._init_pfs.setEnabled(False)
            self._format_exfat.setChecked(False)
        else:
            self.setTitle("Opções de preparo")
            self.setSubTitle("PFS + exFAT + pastas OPL na raiz do volume.")
            self._init_pfs.setEnabled(True)

    def nextId(self) -> int:
        return int(PageId.PREPARE_RUN)

    def validatePage(self) -> bool:
        pfs_only = self._state.mode == WizardMode.PREPARE_PFS
        self._state.init_pfs = True if pfs_only else self._init_pfs.isChecked()
        self._state.format_exfat = False if pfs_only else self._format_exfat.isChecked()
        self._state.scaffold_opl = self._state.format_exfat
        self._state.defer_exfat_format = pfs_only or False
        self._state.cfg_dev = self._cfg_dev.isChecked()
        mbr = Path(self._mbr.text()).expanduser()
        if not pfs_only:
            from ..workflows import ensure_reference_mbr

            try:
                ensure_reference_mbr(mbr)
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "mbr.img",
                    f"Boot FHDB/OPL exige mbr.img do BatchKit Manager:\n{exc}",
                )
                return False
        self._state.reference_mbr = mbr
        if not pfs_only and (
            not self._init_pfs.isChecked() or not self._format_exfat.isChecked()
        ):
            reply = QMessageBox.question(
                self,
                "Boot PS2",
                "Para boot FHDB + OPL BDM como o BatchKit Manager, mantenha "
                "PFS + exFAT/OPL activos. Continuar mesmo assim?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        if self._sudo is not None:
            self._state.sudo_password = self._sudo.text()
            if not is_admin() and not self._state.sudo_password.strip():
                QMessageBox.warning(self, "Senha", "Informe senha sudo ou use sudo ./pfs-batchkit-ui")
                return False
        return True


class ValidateInputPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.VALIDATE_INPUT)
        self._state = state
        self.setTitle("Validar layout OPL")
        self.setSubTitle("Verifica MBR, APAJ e região exFAT num arquivo .img")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._image = QLineEdit(str(_default_image_path_for_ui(state.image_path)))
        form.addRow("Imagem .img:", self._image)
        layout.addLayout(form)
        self._strict = QCheckBox("Strict (aviso = falha)")
        self._require_exfat = QCheckBox("Exigir superblock exFAT formatado")
        layout.addWidget(self._strict)
        layout.addWidget(self._require_exfat)

    def nextId(self) -> int:
        return int(PageId.VALIDATE_RUN)

    def validatePage(self) -> bool:
        path = Path(self._image.text()).expanduser()
        if not path.is_file():
            QMessageBox.warning(self, "Imagem", _image_missing_message(path))
            return False
        self._state.image_path = path
        self._state.validate_strict = self._strict.isChecked()
        self._state.validate_require_exfat = self._require_exfat.isChecked()
        return True


class AdvancedPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.ADVANCED)
        self._state = state
        self.setTitle("Modo avançado")
        self.setSubTitle("Ferramentas CLI equivalentes, sem preparar disco completo.")

        layout = QVBoxLayout(self)
        self._pick = QComboBox()
        self._pick.addItem("Criar imagem híbrida .img (build-image)", AdvancedAction.BUILD_IMAGE)
        self._pick.addItem("Validar layout OPL (.img)", AdvancedAction.VALIDATE)
        self._pick.addItem("Só criar pastas OPL (pasta já montada)", AdvancedAction.SCAFFOLD_OPL)
        layout.addWidget(self._pick)

    def nextId(self) -> int:
        action = self._pick.currentData()
        self._state.advanced_action = AdvancedAction(action)
        if action == AdvancedAction.BUILD_IMAGE:
            return int(PageId.BUILD_INPUT)
        if action == AdvancedAction.VALIDATE:
            self._state.mode = WizardMode.VALIDATE_LAYOUT
            return int(PageId.VALIDATE_INPUT)
        return int(PageId.SCAFFOLD_INPUT)


class BuildInputPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.BUILD_INPUT)
        self._state = state
        self.setTitle("Criar imagem .img")
        self.setSubTitle("Não grava no disco — útil para backup ou validação.")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._size = QDoubleSpinBox()
        self._size.setRange(1, 8192)
        self._size.setValue(state.build_size_gib)
        self._size.setSuffix(" GiB")
        self._out = QLineEdit(str(_default_image_path_for_ui(state.build_output)))
        self._mbr = QLineEdit(str(state.reference_mbr))
        form.addRow("Tamanho total:", self._size)
        form.addRow("Arquivo .img:", self._out)
        form.addRow("mbr.img:", self._mbr)
        layout.addLayout(form)
        self._init_pfs = QCheckBox("init-pfs na imagem")
        self._fmt = QCheckBox("format-exfat na imagem (precisa root/sudo)")
        layout.addWidget(self._init_pfs)
        layout.addWidget(self._fmt)

    def nextId(self) -> int:
        return int(PageId.BUILD_RUN)

    def validatePage(self) -> bool:
        self._state.build_size_gib = float(self._size.value())
        self._state.build_output = Path(self._out.text()).expanduser()
        self._state.reference_mbr = Path(self._mbr.text()).expanduser()
        self._state.build_init_pfs = self._init_pfs.isChecked()
        self._state.build_format_exfat = self._fmt.isChecked()
        return True


class ScaffoldInputPage(BatchKitWizardPage):
    def __init__(self, state: WizardState) -> None:
        super().__init__(PageId.SCAFFOLD_INPUT)
        self._state = state
        self.setTitle("Pastas OPL")
        self.setSubTitle(
            "Só se o exFAT já estiver montado no PC e faltar CD/, DVD/, … "
            "(após «Preparar HDD» isso já foi feito — não precisa repetir). "
            "Use a pasta real do volume PS2OPL, não um disco virtual."
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._mount = QLineEdit(str(state.scaffold_mount))
        form.addRow("Pasta montada (raiz OPL):", self._mount)
        layout.addLayout(form)
        self._cfg_dev = QCheckBox("CFG-DEV")
        layout.addWidget(self._cfg_dev)

    def initializePage(self) -> None:
        found = discover_exfat_volume_root(disk=self._state.selected_disk)
        if found is not None:
            self._mount.setText(str(found))
        else:
            self._mount.setText(
                str(suggest_opl_root_path(disk=self._state.selected_disk))
            )

    def nextId(self) -> int:
        return int(PageId.SCAFFOLD_RUN)

    def validatePage(self) -> bool:
        preferred = Path(self._mount.text()).expanduser()
        resolved, notes = resolve_scaffold_mount(
            preferred,
            disk=self._state.selected_disk,
        )
        if resolved is None:
            QMessageBox.warning(
                self,
                "Pasta montada",
                notes[0] if notes else f"Pasta não encontrada: {preferred}",
            )
            return False
        self._state.scaffold_mount = resolved
        self._mount.setText(str(resolved))
        self._state.cfg_dev = self._cfg_dev.isChecked()
        return True


class AsyncRunPage(BatchKitWizardPage):
    """Base for worker-backed pages — Avançar só após sucesso."""

    def __init__(
        self,
        state: WizardState,
        page_id: PageId,
        title: str,
        subtitle: str,
        worker_cls: Type,
        next_done_id: PageId,
    ) -> None:
        super().__init__(page_id)
        self._state = state
        self.setTitle(title)
        self.setSubTitle(subtitle)
        self._worker_cls = worker_cls
        self._next_done_id = next_done_id
        self._started = False
        self._ok = False
        self._last_pct_log = -1
        self._worker = None
        self._finish_generation = 0

        layout = QVBoxLayout(self)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._progress)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

    def nextId(self) -> int:
        return int(self._next_done_id)

    def validatePage(self) -> bool:
        if self._ok:
            return True
        QMessageBox.information(
            self,
            "Operação",
            "A etapa ainda não terminou com sucesso. Aguarde o log ou use «Voltar» "
            "para ajustar opções.",
        )
        return False

    def worker_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def wait_for_worker(self, msec: int = -1) -> bool:
        if self._worker is None or not self._worker.isRunning():
            return True
        return self._worker.wait(msec)

    def _set_wizard_buttons_running(self, running: bool) -> None:
        wizard = self.wizard()
        if not wizard:
            return
        if running:
            wizard.button(QWizard.WizardButton.NextButton).setEnabled(False)
            wizard.button(QWizard.WizardButton.BackButton).setEnabled(False)
            wizard.button(QWizard.WizardButton.CancelButton).setEnabled(False)
        else:
            wizard.button(QWizard.WizardButton.CancelButton).setEnabled(True)
            wizard.button(QWizard.WizardButton.NextButton).setEnabled(self._ok)
            wizard.button(QWizard.WizardButton.BackButton).setEnabled(not self._ok)

    def initializePage(self) -> None:
        if self._started and self._ok and not self.worker_running():
            self._set_wizard_buttons_running(False)
            self.completeChanged.emit()
            return

        if self.worker_running():
            self._set_wizard_buttons_running(True)
            self.completeChanged.emit()
            return

        self._ok = False
        self._last_pct_log = -1
        self._state.exit_code = 2
        self._state.log_lines.clear()
        self._log.clear()
        self._progress.setRange(0, 0)
        self._set_wizard_buttons_running(True)
        self.completeChanged.emit()

        self._started = True
        self._finish_generation += 1
        run_generation = self._finish_generation
        if self._worker is not None:
            self.wait_for_worker()
            try:
                self._worker.line.disconnect(self._on_line)
            except (TypeError, RuntimeError):
                pass
            try:
                self._worker.progress.disconnect(self._on_byte_progress)
            except (TypeError, RuntimeError, AttributeError):
                pass
        self._worker = self._worker_cls(self._state)
        self._worker.setParent(self)
        self._worker.line.connect(self._on_line)
        self._worker.finished_with_code.connect(
            lambda code, gen=run_generation: self._on_finished(code, gen)
        )
        if hasattr(self._worker, "progress"):
            self._worker.progress.connect(self._on_byte_progress)
        self._worker.start()

    def cleanupPage(self) -> None:
        self.wait_for_worker()
        if not self._ok:
            self._started = False
            self._worker = None

    def _on_line(self, line: str) -> None:
        self._log.append(line)
        self._state.log_lines.append(line)

    def _on_byte_progress(self, done: int, total: int) -> None:
        if total <= 0:
            return
        if self._progress.maximum() != 1000:
            self._progress.setRange(0, 1000)
        self._progress.setValue(min(1000, done * 1000 // total))
        pct = done * 100 // total
        if pct >= self._last_pct_log + 5 or pct >= 99:
            self._last_pct_log = pct
            gib_done = done / (1024**3)
            gib_total = total / (1024**3)
            self._log.append(f"Progresso: {pct}% ({gib_done:.1f} / {gib_total:.1f} GiB)")

    def _on_finished(self, code: int, generation: int) -> None:
        if generation != self._finish_generation:
            return
        self._state.exit_code = code
        self._ok = code == 0
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._set_wizard_buttons_running(False)
        if code == 0:
            self.setSubTitle("Concluído — clique Avançar para o resumo final.")
        elif code == 1:
            self.setSubTitle("Avisos no log — use «Voltar» ou ajuste opções strict.")
            QMessageBox.warning(
                self,
                "Strict",
                "Validação concluída com avisos — no modo strict isso conta como falha. Veja o log.",
            )
        else:
            self.setSubTitle("Falhou — use «Voltar» para corrigir e tente de novo.")
            QMessageBox.critical(self, "Falha", "Operação falhou — veja o log.")
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._ok and not self.worker_running()


class SummaryPage(BatchKitWizardPage):
    def __init__(
        self,
        state: WizardState,
        page_id: PageId,
        title: str,
        subtitle: str,
        extra_html: str = "",
    ) -> None:
        super().__init__(page_id)
        self._state = state
        self.setTitle(title)
        self.setSubTitle(subtitle)
        self._extra_html = extra_html

        layout = QVBoxLayout(self)
        self._body = QLabel()
        self._body.setWordWrap(True)
        layout.addWidget(self._body)
        if extra_html:
            extra = QLabel(extra_html)
            extra.setWordWrap(True)
            extra.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(extra)

    def nextId(self) -> int:
        return -1

    def isCommitPage(self) -> bool:
        return True

    def initializePage(self) -> None:
        tail = "\n".join(self._state.log_lines[-14:])
        self._body.setText(tail or "Concluído.")
        wizard = self.wizard()
        if wizard is not None:
            wizard.button(QWizard.WizardButton.BackButton).setEnabled(False)


class PrepareDonePage(SummaryPage):
    """Resumo após prepare-device."""

    def __init__(self, state: WizardState) -> None:
        super().__init__(
            state,
            PageId.PREPARE_DONE,
            "HDD preparado",
            "Última etapa — clique Fechar para sair do assistente.",
            FINISH_HTML,
        )

    def initializePage(self) -> None:
        super().initializePage()
        if self._state.mode == WizardMode.PREPARE_PFS:
            self.setTitle("PFS atualizado")
            self.setSubTitle("Última etapa — clique Fechar para sair do assistente.")
            return
        self.setSubTitle("Última etapa — clique Fechar para sair do assistente.")
        if self._state.format_exfat and self._state.scaffold_opl:
            root = discover_opl_root(
                disk=self._state.selected_disk,
                extra_paths=(self._state.opl_root,),
            )
            if root is not None:
                self._state.opl_root = root
            else:
                root = suggest_opl_root_path(disk=self._state.selected_disk)
            tail = (self._body.text() or "").rstrip()
            self._body.setText(f"{tail}\n\nRaiz OPL no PC: {root}")


def make_run_pages(state: WizardState) -> list[QWizardPage]:
    return [
        AsyncRunPage(
            state,
            PageId.PREPARE_RUN,
            "Preparando disco",
            "Aguarde — não desconecte o HDD.",
            PrepareDiskWorker,
            PageId.PREPARE_DONE,
        ),
        AsyncRunPage(
            state,
            PageId.VALIDATE_RUN,
            "Validando",
            "Analisando layout…",
            ValidateLayoutWorker,
            PageId.VALIDATE_DONE,
        ),
        AsyncRunPage(
            state,
            PageId.BUILD_RUN,
            "Criando imagem",
            "Pode demorar em discos grandes…",
            BuildImageWorker,
            PageId.BUILD_DONE,
        ),
        AsyncRunPage(
            state,
            PageId.SCAFFOLD_RUN,
            "Criando pastas",
            "OPL tree…",
            ScaffoldOplWorker,
            PageId.SCAFFOLD_DONE,
        ),
    ]


FINISH_HTML = (
    "<p><b>PC:</b> layout APA-Jail + exFAT OPL validado (como PFS-BatchKit-Manager).</p>"
    "<p><b>Primeiro boot no PS2:</b> abre <b>wLaunchELF</b> (loader do <code>mbr.img</code>) — "
    "isso é normal; ainda <i>não</i> é o menu OSD do FreeHDBoot.</p>"
    "<p><b>Depois (uma vez no PS2):</b> mass: → APPS → FreeMcBoot → "
    "<b>FMCBInstaller.elf</b> → R1 → <b>Install FHDB (From HDD)</b>. "
    "Reinicie: aí sim boot FHDB + menu OSD; OPL em APPS/OPL (BDM HDD).</p>"
    "<p>Não use Format/Expand no HDD Manager do wLaunchELF.</p>"
    "<p>OPL Manager: <code>OPL_FOLDER</code> = raiz montada PS2OPL.</p>"
)
