"""Entry point for the desktop app.

The local SQLite DB (WAL mode) and a NoOpSyncProvider (unused until Cycle 4's
sync worker exists) are wired up on startup. Reception and Doctor screens
share one real UdpBroadcaster so queue-token changes reach LAN display
clients (display_sim, or real hardware later) with no code change between
the two.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from common.sync_provider import NoOpSyncProvider
from desktop.broadcast.udp_broadcaster import UdpBroadcaster
from desktop.data.db import connect, migrate
from desktop.ui.doctor_window import DoctorWindow
from desktop.ui.reception_window import ReceptionWindow


class MainWindow(QMainWindow):
    def __init__(self, db_path=None) -> None:
        super().__init__()
        self.setWindowTitle("Hybrid Offline-First HMS")
        self.resize(480, 320)

        self.conn = connect(db_path) if db_path else connect()
        migrate(self.conn)
        self.sync_provider = NoOpSyncProvider()
        self.broadcaster = UdpBroadcaster()

        tabs = QTabWidget()
        tabs.addTab(ReceptionWindow(self.conn, broadcaster=self.broadcaster), "Reception")
        tabs.addTab(DoctorWindow(self.conn, broadcaster=self.broadcaster), "Doctor")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        self.broadcaster.close()
        self.conn.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
