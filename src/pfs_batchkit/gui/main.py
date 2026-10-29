"""Qt GUI entry (installer wizard)."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "Interface gráfica requer PySide6. Instale com:\n"
            "  pip install 'pfs-batchkit[gui]'\n"
            "  # ou: pip install PySide6",
            file=sys.stderr,
        )
        return 1

    from .wizard import PS2HddWizard

    app = QApplication(sys.argv)
    app.setApplicationName("PFS BatchKit")
    wizard = PS2HddWizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
