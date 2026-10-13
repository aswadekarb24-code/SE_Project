"""Entry point for the desktop app.

The local SQLite DB (WAL mode) and a NoOpSyncProvider (unused until Cycle 4's
sync worker exists) are wired up on startup; the Reception check-in screen
(Cycle 1) is the first real feature.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from common.sync_provider import NoOpSyncProvider
from desktop.data.db import connect, migrate
from desktop.ui.reception_window import ReceptionWindow


class MainWindow(QMainWindow):
    def __init__(self, db_path=None) -> None:
        super().__init__()
        self.setWindowTitle("Hybrid Offline-First HMS")
        self.resize(480, 320)

        self.conn = connect(db_path) if db_path else connect()
        migrate(self.conn)
        self.sync_provider = NoOpSyncProvider()

        self.setCentralWidget(ReceptionWindow(self.conn))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        self.conn.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
