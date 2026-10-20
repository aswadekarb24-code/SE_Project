"""Entry point for the desktop app.

The local SQLite DB (WAL mode) is migrated and seeded with MVP reference
data on startup. The sync layer defaults to NoOpSyncProvider -- fully
offline -- unless HMS_GATEWAY_URL is set (desktop/config.py), in which case
a real FastAPISyncProvider drives a background SyncScheduler. A role is
chosen at launch (Receptionist or Doctor), and only that role's screens are
shown -- see desktop/services/auth_service.py for why this is UI-level
gating, not a full auth system.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from common.sync_provider import NoOpSyncProvider
from desktop.broadcast.udp_broadcaster import UdpBroadcaster
from desktop.config import GATEWAY_URL, SYNC_INTERVAL_SECONDS
from desktop.data.db import connect, migrate
from desktop.data.seed import seed_default_data
from desktop.services.auth_service import Role
from desktop.sync.providers.fastapi_provider import FastAPISyncProvider
from desktop.sync.sync_scheduler import SyncScheduler
from desktop.sync.sync_worker import SyncWorker
from desktop.ui.doctor_window import DoctorWindow
from desktop.ui.reception_window import ReceptionWindow
from desktop.ui.role_select_dialog import RoleSelectDialog
from desktop.ui.theme import apply_theme, style_combo_popups
from desktop.ui.widgets.bed_matrix_widget import BedMatrixWidget
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


class MainWindow(QMainWindow):
    def __init__(self, db_path=None, role: Role | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Hybrid Offline-First HMS")
        self.resize(1120, 720)
        # Visual only: a strip of canvas around the rounded app shell.
        self.setContentsMargins(16, 16, 16, 16)

        self.conn = connect(db_path) if db_path else connect()
        migrate(self.conn)
        seed_default_data(self.conn)
        self.broadcaster = UdpBroadcaster()

        self.sync_provider = FastAPISyncProvider(GATEWAY_URL) if GATEWAY_URL else NoOpSyncProvider()
        self.sync_worker = SyncWorker(self.conn, self.sync_provider)
        self.sync_scheduler = SyncScheduler(
            self.sync_worker, interval_seconds=SYNC_INTERVAL_SECONDS
        )
        self.sync_scheduler.start()

        self.role = role if role is not None else self._prompt_for_role()
        self.setCentralWidget(self._build_tabs_for_role(self.role))
        style_combo_popups(self)

    def _prompt_for_role(self) -> Role:
        dialog = RoleSelectDialog(self)
        dialog.exec()
        return dialog.selected_role or Role.RECEPTIONIST

    def _build_tabs_for_role(self, role: Role) -> QTabWidget:
        tabs = QTabWidget()
        # Lets the stylesheet paint the rounded shell behind tabs + pane.
        tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if role == Role.RECEPTIONIST:
            tabs.addTab(ReceptionWindow(self.conn, broadcaster=self.broadcaster), "Reception")
            tabs.addTab(BedMatrixWidget(self.conn), "Beds")
            tabs.addTab(PharmacyWidget(self.conn), "Pharmacy")
        else:
            tabs.addTab(DoctorWindow(self.conn, broadcaster=self.broadcaster), "Doctor Console")
            tabs.addTab(DoctorAvailabilityWidget(self.conn), "Doctor Availability")
        return tabs

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        self.sync_scheduler.stop()
        self.broadcaster.close()
        self.conn.close()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
