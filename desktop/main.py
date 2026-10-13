"""Entry point for the desktop app.

The local SQLite DB (WAL mode) is migrated and seeded with MVP reference
data on startup; a NoOpSyncProvider is wired up (unused until Cycle 4's sync
worker exists). A role is chosen at launch (Receptionist or Doctor), and only
that role's screens are shown -- see desktop/services/auth_service.py for
why this is UI-level gating, not a full auth system.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

from common.sync_provider import NoOpSyncProvider
from desktop.broadcast.udp_broadcaster import UdpBroadcaster
from desktop.data.db import connect, migrate
from desktop.data.seed import seed_default_data
from desktop.services.auth_service import Role
from desktop.ui.doctor_window import DoctorWindow
from desktop.ui.reception_window import ReceptionWindow
from desktop.ui.role_select_dialog import RoleSelectDialog
from desktop.ui.widgets.bed_matrix_widget import BedMatrixWidget
from desktop.ui.widgets.doctor_availability_widget import DoctorAvailabilityWidget
from desktop.ui.widgets.pharmacy_widget import PharmacyWidget


class MainWindow(QMainWindow):
    def __init__(self, db_path=None, role: Role | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Hybrid Offline-First HMS")
        self.resize(480, 320)

        self.conn = connect(db_path) if db_path else connect()
        migrate(self.conn)
        seed_default_data(self.conn)
        self.sync_provider = NoOpSyncProvider()
        self.broadcaster = UdpBroadcaster()

        self.role = role if role is not None else self._prompt_for_role()
        self.setCentralWidget(self._build_tabs_for_role(self.role))

    def _prompt_for_role(self) -> Role:
        dialog = RoleSelectDialog(self)
        dialog.exec()
        return dialog.selected_role or Role.RECEPTIONIST

    def _build_tabs_for_role(self, role: Role) -> QTabWidget:
        tabs = QTabWidget()
        if role == Role.RECEPTIONIST:
            tabs.addTab(ReceptionWindow(self.conn, broadcaster=self.broadcaster), "Reception")
            tabs.addTab(BedMatrixWidget(self.conn), "Beds")
            tabs.addTab(PharmacyWidget(self.conn), "Pharmacy")
        else:
            tabs.addTab(DoctorWindow(self.conn, broadcaster=self.broadcaster), "Doctor Console")
            tabs.addTab(DoctorAvailabilityWidget(self.conn), "Doctor Availability")
        return tabs

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
