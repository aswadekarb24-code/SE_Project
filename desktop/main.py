"""Entry point for the desktop app.

The local SQLite DB (WAL mode) is migrated and seeded with MVP reference
data on startup. The sync layer defaults to NoOpSyncProvider -- fully
offline -- unless HMS_GATEWAY_URL is set (desktop/config.py), in which case
a real FastAPISyncProvider drives a background SyncScheduler.

The window opens on the sign-in screen. Signing in builds the workspace
for that account's role (desktop/ui/app_shell.py); logging out tears it
down and returns to sign-in, so nothing from one user's session is left
on screen for the next.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from common.sync_provider import NoOpSyncProvider
from desktop.broadcast.udp_broadcaster import UdpBroadcaster
from desktop.config import GATEWAY_URL, STARTUP_SYNC_DELAY_SECONDS, SYNC_INTERVAL_SECONDS
from desktop.data.db import connect, migrate
from desktop.data.seed import seed_default_data
from desktop.services.auth_service import AuthenticatedUser
from desktop.services.doctor_service import broadcast_all_doctors
from desktop.sync.providers.fastapi_provider import FastAPISyncProvider
from desktop.sync.sync_scheduler import SyncScheduler
from desktop.sync.sync_worker import SyncWorker
from desktop.ui.app_shell import AppShell
from desktop.ui.auth_page import AuthPage
from desktop.ui.theme import apply_theme

APP_TITLE = "Hybrid Offline-First HMS"
# How often every doctor's status is re-broadcast, so a display that
# started late or missed a UDP packet catches up.
DOCTOR_HEARTBEAT_MS = 30_000


class MainWindow(QMainWindow):
    def __init__(self, db_path=None, user: AuthenticatedUser | None = None) -> None:
        """`user` skips the sign-in screen (used by tests)."""
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1260, 760)
        self.setMinimumSize(1100, 700)
        # A strip of canvas around the rounded app shell.
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
        self.startup_sync = QTimer(self)
        self.startup_sync.setSingleShot(True)
        self.startup_sync.setInterval(int(STARTUP_SYNC_DELAY_SECONDS * 1000))
        self.startup_sync.timeout.connect(self.sync_scheduler.sync_now)
        self.startup_sync.start()

        self.doctor_heartbeat = QTimer(self)
        self.doctor_heartbeat.setInterval(DOCTOR_HEARTBEAT_MS)
        self.doctor_heartbeat.timeout.connect(
            lambda: broadcast_all_doctors(self.conn, self.broadcaster)
        )
        self.doctor_heartbeat.start()

        self.screens = QStackedWidget()
        self.auth_page = AuthPage(self.conn)
        self.auth_page.authenticated.connect(self.sign_in)
        self.screens.addWidget(self.auth_page)
        self.setCentralWidget(self.screens)
        self.shell: AppShell | None = None

        if user is not None:
            self.sign_in(user)

    @property
    def user(self) -> AuthenticatedUser | None:
        return self.shell.user if self.shell else None

    def sign_in(self, user: AuthenticatedUser) -> None:
        self._discard_shell()
        self.shell = AppShell(
            self.conn,
            user,
            self.broadcaster,
            sync_scheduler=self.sync_scheduler,
            gateway_url=GATEWAY_URL,
        )
        self.shell.logout_requested.connect(self.logout)
        self.screens.addWidget(self.shell)
        self.screens.setCurrentWidget(self.shell)
        self.setWindowTitle(f"{APP_TITLE} · {user.display_name}")

    def logout(self) -> None:
        self._discard_shell()
        self.auth_page.reset()
        self.screens.setCurrentWidget(self.auth_page)
        self.setWindowTitle(APP_TITLE)

    def _discard_shell(self) -> None:
        if self.shell is not None:
            self.shell.sync_chip.stop()
            self.screens.removeWidget(self.shell)
            self.shell.deleteLater()
            self.shell = None

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        self.sync_scheduler.stop()
        self.startup_sync.stop()
        self.doctor_heartbeat.stop()
        self._discard_shell()  # stops the workspace's timers before the DB closes
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
