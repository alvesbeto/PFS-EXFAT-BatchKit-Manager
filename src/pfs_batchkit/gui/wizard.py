"""Qt installer-style wizard — multi-flow PS2 HDD assistant."""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox, QWizard

from .. import __version__
from .page_ids import PageId
from .state import WizardState
from .wizard_pages import (
    AdvancedPage,
    BuildInputPage,
    DiskSelectPage,
    FinalizeDonePage,
    FinalizeOptionsPage,
    GamesDonePage,
    GamesInputPage,
    PrepareDonePage,
    PrepareOptionsPage,
    ScaffoldInputPage,
    SummaryPage,
    ValidateInputPage,
    WelcomePage,
    make_run_pages,
)


class PS2HddWizard(QWizard):
    def __init__(self) -> None:
        super().__init__()
        self._state = WizardState()
        self.setWindowTitle(f"PFS BatchKit {__version__} — Assistente HDD PS2")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoCancelButtonOnLastPage, True)
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage, True)
        self.setOption(QWizard.WizardOption.IndependentPages, True)
        self.resize(760, 560)

        pages: list = [
            WelcomePage(self._state),
            DiskSelectPage(self._state),
            PrepareOptionsPage(self._state),
            FinalizeOptionsPage(self._state),
            GamesInputPage(self._state),
            *make_run_pages(self._state),
            PrepareDonePage(self._state),
            FinalizeDonePage(self._state),
            GamesDonePage(self._state),
            ValidateInputPage(self._state),
            SummaryPage(
                self._state,
                PageId.VALIDATE_DONE,
                "Validação concluída",
                "Revise o relatório acima.",
            ),
            AdvancedPage(self._state),
            BuildInputPage(self._state),
            SummaryPage(
                self._state,
                PageId.BUILD_DONE,
                "Imagem criada",
                "Use «Validar layout» ou prepare o disco físico in-place.",
            ),
            ScaffoldInputPage(self._state),
            SummaryPage(
                self._state,
                PageId.SCAFFOLD_DONE,
                "Pastas OPL criadas",
                "Copie ISOs com OPL Manager ou pelo explorador de ficheiros.",
            ),
        ]

        for page in pages:
            self.setPage(page.pageId(), page)

        self.setStartId(int(PageId.WELCOME))
        self.setButtonText(QWizard.WizardButton.NextButton, "Avançar →")
        self.setButtonText(QWizard.WizardButton.BackButton, "← Voltar")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Fechar")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")

    def _async_run_page(self):
        from .wizard_pages import AsyncRunPage

        page = self.currentPage()
        return page if isinstance(page, AsyncRunPage) else None

    def _confirm_abort_async(self) -> bool:
        page = self._async_run_page()
        if page is None or not page.worker_running():
            return True
        reply = QMessageBox.question(
            self,
            "Cancelar",
            "Operação em andamento. Cancelar mesmo assim?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        page.wait_for_worker()
        return True

    def reject(self) -> None:
        if not self._confirm_abort_async():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_abort_async():
            event.ignore()
            return
        super().closeEvent(event)
