"""The signed-in workspace: floating icon sidebar, page header with the
user and a log-out button, and the role's pages.

Which pages exist is decided by the signed-in account's role:
receptionists get intake, queue, beds and pharmacy; doctors get
consultations, patient records (with reports) and availability.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
)

from common import design_tokens as tokens
from common.clock import local_today
from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.auth_service import AuthenticatedUser, Role
from desktop.sync.sync_scheduler import SyncScheduler
from desktop.sync.sync_status import sync_snapshot
from desktop.ui import icons
from desktop.ui.components import Avatar, button, label, repolish
from desktop.ui.day_overview import DayOverviewDialog
from desktop.ui.pages.base import Page
from desktop.ui.pages.check_in_page import CheckInPage
from desktop.ui.pages.doctor_console import DoctorConsole
from desktop.ui.pages.patients_page import PatientsPage
from desktop.ui.pages.reception_dashboard import ReceptionDashboard
from desktop.ui.pages.simple_pages import AvailabilityPage, BedsPage, DoctorsPage, PharmacyPage

PageFactory = Callable[[sqlite3.Connection, AuthenticatedUser, Broadcaster | None], Page]

# (key, sidebar tooltip, icon, factory) per role, in sidebar order.
NAVIGATION: dict[Role, list[tuple[str, str, str, PageFactory]]] = {
    Role.RECEPTIONIST: [
        ("dashboard", "Dashboard", "dashboard", lambda c, u, b: ReceptionDashboard(c, u)),
        ("check_in", "Check-in", "user-plus", lambda c, u, b: CheckInPage(c, u, b)),
        ("patients", "Patients", "users", lambda c, u, b: PatientsPage(c, u)),
        ("doctors", "Doctors", "stethoscope", lambda c, u, b: DoctorsPage(c, u)),
        ("beds", "Beds", "bed", lambda c, u, b: BedsPage(c, u)),
        ("pharmacy", "Pharmacy", "pill", lambda c, u, b: PharmacyPage(c, u)),
    ],
    Role.DOCTOR: [
        ("console", "Consultations", "stethoscope", lambda c, u, b: DoctorConsole(c, u, b)),
        ("patients", "Patients", "users", lambda c, u, b: PatientsPage(c, u)),
        (
            "availability",
            "Availability",
            "calendar-check",
            lambda c, u, b: AvailabilityPage(c, u, b),
        ),
    ],
}


class SyncChip(QFrame):
    """Sync status bar: coloured dot + label (blue synced, orange offline,
    red conflict/error), details in the tooltip, and a Retry button.
    """

    REFRESH_MS = 5_000

    def __init__(
        self,
        conn: sqlite3.Connection,
        scheduler: SyncScheduler | None,
        gateway_url: str | None,
    ) -> None:
        super().__init__()
        self.setObjectName("syncChip")
        self.setFixedHeight(38)
        self._conn = conn
        self._scheduler = scheduler
        self._gateway_url = gateway_url

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 6, 0)
        layout.setSpacing(8)
        self.dot = label("", "syncDot")
        self.dot.setFixedSize(8, 8)
        self.text_label = label("", "syncText")
        self.retry_button = QToolButton()
        self.retry_button.setObjectName("syncRetry")
        self.retry_button.setIcon(icons.icon("refresh", tokens.TEXT_SECONDARY, size=16))
        self.retry_button.setIconSize(QSize(16, 16))
        self.retry_button.setFixedSize(28, 28)
        self.retry_button.setToolTip("Sync now")
        self.retry_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.retry_button.clicked.connect(self.retry)
        self.retry_button.setEnabled(scheduler is not None and gateway_url is not None)
        layout.addWidget(self.dot)
        layout.addWidget(self.text_label)
        layout.addWidget(self.retry_button)

        if scheduler is not None:
            scheduler.ran.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.setInterval(self.REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def refresh(self) -> None:
        scheduler = self._scheduler
        snapshot = sync_snapshot(
            self._conn,
            gateway_url=self._gateway_url,
            state=scheduler.state if scheduler else None,
            last_attempt_at=scheduler.last_attempt_at if scheduler else None,
            last_results=scheduler.last_results if scheduler else [],
            last_error=scheduler.last_error if scheduler else None,
        )
        self.text_label.setText(snapshot.label)
        self.setToolTip(snapshot.detail)
        if self.property("tone") != snapshot.tone:
            for widget in (self, self.dot, self.text_label):
                widget.setProperty("tone", snapshot.tone)
                repolish(widget)

    def retry(self) -> None:
        if self._scheduler is not None:
            self._scheduler.sync_now()
        self.refresh()

    def stop(self) -> None:
        """Stop polling. Called when the workspace is torn down, so the timer
        can never query a database connection that's about to close.
        """
        self._timer.stop()
        if self._scheduler is not None:
            self._scheduler.ran.disconnect(self.refresh)


class AppShell(QFrame):
    logout_requested = pyqtSignal()

    def __init__(
        self,
        conn: sqlite3.Connection,
        user: AuthenticatedUser,
        broadcaster: Broadcaster | None = None,
        *,
        sync_scheduler: SyncScheduler | None = None,
        gateway_url: str | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("shell")
        self.user = user
        self._conn = conn
        self.sync_chip = SyncChip(conn, sync_scheduler, gateway_url)
        self.pages: dict[str, Page] = {}
        self.nav_buttons: dict[str, QToolButton] = {}
        self.nav_labels: list[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 24, 20)
        layout.setSpacing(22)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(76)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 16, 14, 16)
        side.setSpacing(10)
        logo = label("", "logoChip")
        logo.setFixedSize(46, 46)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(icons.pixmap("logo", tokens.TEXT_ON_ACCENT, 22))
        logo.setToolTip("Hybrid Offline-First HMS")
        side.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        side.addSpacing(18)

        self.stack = QStackedWidget()
        group = QButtonGroup(self)
        group.setExclusive(True)
        for number, (key, title, icon_name, factory) in enumerate(NAVIGATION[user.role], 1):
            page = factory(conn, user, broadcaster)
            page.navigate.connect(self.open)
            self.pages[key] = page
            self.stack.addWidget(page)

            nav = QToolButton()
            nav.setObjectName("navButton")
            nav.setCheckable(True)
            nav.setIcon(
                icons.icon(icon_name, tokens.TEXT_SECONDARY, checked_color=tokens.PRIMARY, size=22)
            )
            nav.setIconSize(QSize(22, 22))
            nav.setFixedSize(46, 46)
            nav.setToolTip(f"{title}  (Ctrl+{number})")
            QShortcut(
                QKeySequence(f"Ctrl+{number}"), self, activated=lambda k=key: self.show_page(k)
            )
            nav.setAccessibleName(title)
            nav.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            nav.clicked.connect(lambda _checked, k=key: self.show_page(k))
            group.addButton(nav)
            side.addWidget(nav, 0, Qt.AlignmentFlag.AlignHCenter)
            self.nav_buttons[key] = nav
            self.nav_labels.append(title)
        side.addStretch(1)
        layout.addWidget(sidebar)

        main = QVBoxLayout()
        main.setSpacing(20)
        main.addLayout(self._build_header())
        main.addWidget(self.stack, 1)
        layout.addLayout(main, 1)

        if "check_in" in self.pages:
            QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_patient)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)

        self.show_page(NAVIGATION[user.role][0][0])

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title_label = label("", "pageTitle")
        self.subtitle_label = label("", "pageSubtitle", wrap=True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        header.addLayout(titles, 1)

        self.date_button = button("", "secondary", "calendar-check")
        self.date_button.setObjectName("dateChip")
        self.date_button.setFixedHeight(38)
        self.date_button.setToolTip("Open the calendar: patients and reports by day")
        self.date_button.clicked.connect(self.open_calendar)
        self._update_date()
        header.addWidget(self.date_button, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.sync_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        chip = QFrame()
        chip.setObjectName("userChip")
        chip.setFixedHeight(48)
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(6, 6, 16, 6)
        chip_layout.setSpacing(10)
        chip_layout.addWidget(Avatar(self.user.display_name, 34))
        who = QVBoxLayout()
        who.setSpacing(0)
        who.addWidget(label(self.user.display_name, "chipName"))
        role_text = self.user.role.label
        who.addWidget(label(role_text, "chipRole"))
        chip_layout.addLayout(who)
        header.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.logout_button = button("Log out", "secondary", "logout")
        self.logout_button.setObjectName("pillButton")
        self.logout_button.clicked.connect(self.logout_requested.emit)
        header.addWidget(self.logout_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return header

    @property
    def current_key(self) -> str:
        page = self.stack.currentWidget()
        return next(key for key, value in self.pages.items() if value is page)

    def show_page(self, key: str) -> None:
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        self._update_date()  # stays right if the app is left open past midnight
        self.title_label.setText(page.title)
        self.subtitle_label.setText(page.subtitle)
        page.refresh()

    def _update_date(self) -> None:
        today = local_today()
        self.date_button.setText(f"{today:%a}, {today.day} {today:%b %Y}")

    def open_calendar(self) -> None:
        """The date chip's calendar: browse any day's patients and reports."""
        dialog = DayOverviewDialog(self._conn, self.user, self)
        dialog.open_patient.connect(lambda patient_id: self.open("patients", patient_id))
        dialog.exec()

    def new_patient(self) -> None:
        """Ctrl+N: jump to check-in with the cursor in the full-name field."""
        self.show_page("check_in")
        self.pages["check_in"].focus_new_patient()

    def focus_search(self) -> None:
        """Ctrl+F: focus the current page's search box, if it has one."""
        page = self.stack.currentWidget()
        if hasattr(page, "focus_search"):
            page.focus_search()

    def open(self, key: str, patient_id: object = None) -> None:
        """Handle a page's navigate request, optionally opening a patient."""
        if key not in self.pages:
            return
        self.show_page(key)
        if patient_id and isinstance(self.pages[key], PatientsPage):
            self.pages[key].select_patient(str(patient_id))
