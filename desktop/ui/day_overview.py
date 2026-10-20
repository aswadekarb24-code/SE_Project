"""Calendar behind the header's date chip: pick any day to see who visited,
who registered and (for doctors) which reports were written. Days with
activity are highlighted. Double-click a patient to open their record, or
a report to read / export it.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from common import design_tokens as tokens
from common.clock import local_today
from desktop.services.auth_service import AuthenticatedUser, Role
from desktop.services.day_service import active_days, day_overview, local_time
from desktop.services.patient_service import age_sex, get_patient
from desktop.ui.components import (
    Badge,
    Segmented,
    button,
    cell,
    empty_state,
    label,
    person_cell,
    table,
    table_item,
)
from desktop.ui.date_field import styled_calendar, to_date
from desktop.ui.report_dialogs import ReportViewerDialog


def _fixed(table_widget: QTableWidget, widths: dict[int, int]) -> None:
    header = table_widget.horizontalHeader()
    for column, width in widths.items():
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        table_widget.setColumnWidth(column, width)


class DayOverviewDialog(QDialog):
    # Ask the shell to open this patient's record.
    open_patient = pyqtSignal(str)

    def __init__(
        self,
        conn: sqlite3.Connection,
        user: AuthenticatedUser,
        parent: QWidget | None = None,
        *,
        day: date | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Day overview")
        self.setModal(True)
        self.resize(1180, 660)
        self._conn = conn
        self._include_reports = user.role == Role.DOCTOR
        self._overview: dict = {"visits": [], "registrations": [], "reports": []}
        self._highlighted: set[date] = set()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(24)

        # Calendar ---------------------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(label("Pick a day", "dialogTitle"))
        today = local_today()
        self.calendar = styled_calendar(maximum=today)
        self.calendar.setObjectName("dayCalendar")
        self.calendar.setFixedSize(330, 290)
        left.addWidget(self.calendar)
        today_button = button("Today", "secondary", "calendar-check")
        today_button.clicked.connect(lambda: self.show_day(local_today()))
        left.addWidget(today_button)
        left.addWidget(label("Bold dates had visits or reports.", "muted", wrap=True))
        left.addStretch(1)
        layout.addLayout(left)

        # The day ------------------------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(14)
        heading = QHBoxLayout()
        self.day_label = label("", "dialogTitle")
        heading.addWidget(self.day_label)
        heading.addStretch(1)
        self.visits_badge = Badge("", "info")
        self.registrations_badge = Badge("", "success")
        heading.addWidget(self.visits_badge)
        heading.addWidget(self.registrations_badge)
        self.reports_badge = Badge("", "neutral")
        if self._include_reports:
            heading.addWidget(self.reports_badge)
        right.addLayout(heading)

        tabs = ["Visits", "New patients"] + (["Reports"] if self._include_reports else [])
        self.tabs = Segmented(tabs)
        right.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignLeft)

        self.visits_table = table(["Time", "Token", "Patient", "Department", "Status"])
        _fixed(self.visits_table, {0: 90, 1: 70, 3: 150, 4: 130})
        self.registrations_table = table(["Time", "Patient", "Age · Sex", "Phone"])
        _fixed(self.registrations_table, {0: 90, 2: 130, 3: 170})
        self.reports_table = table(["Time", "Report no.", "Patient", "Diagnosis", "Doctor"])
        _fixed(self.reports_table, {0: 90, 1: 160, 4: 135})

        self.stack = QStackedWidget()
        self._pages = []
        for table_widget, empty_title in (
            (self.visits_table, "No visits on this day"),
            (self.registrations_table, "No new patients on this day"),
            (self.reports_table, "No reports on this day"),
        ):
            page = QStackedWidget()
            page.addWidget(table_widget)
            page.addWidget(empty_state(empty_title, "Pick another day in the calendar.", "clock"))
            self._pages.append(page)
            self.stack.addWidget(page)
        right.addWidget(self.stack, 1)
        for index, option in enumerate(self.tabs.buttons):
            option.toggled.connect(lambda on, i=index: on and self.stack.setCurrentIndex(i))

        footer = QHBoxLayout()
        self.hint_label = label("Double-click a row to open it.", "muted")
        footer.addWidget(self.hint_label)
        footer.addStretch(1)
        close = button("Close")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        right.addLayout(footer)
        layout.addLayout(right, 1)

        for table_widget in (self.visits_table, self.registrations_table):
            table_widget.doubleClicked.connect(
                lambda index, t=table_widget: self._open_patient_at(t, index.row())
            )
        self.reports_table.doubleClicked.connect(lambda index: self._view_report(index.row()))
        self.calendar.selectionChanged.connect(
            lambda: self._load(to_date(self.calendar.selectedDate()))
        )
        self.calendar.currentPageChanged.connect(lambda year, month: self._highlight(year, month))

        self.show_day(day or today)

    # Data -----------------------------------------------------------------
    def show_day(self, day: date) -> None:
        self.calendar.setSelectedDate(QDate(day.year, day.month, day.day))
        self._highlight(day.year, day.month)
        self._load(day)

    def _highlight(self, year: int, month: int) -> None:
        """Bold, blue dates for days with activity in the shown month."""
        for old in self._highlighted:
            self.calendar.setDateTextFormat(QDate(old.year, old.month, old.day), QTextCharFormat())
        first = date(year, month, 1)
        last = date(year + month // 12, month % 12 + 1, 1)
        busy = active_days(self._conn, first, last)
        marked = QTextCharFormat()
        marked.setFontWeight(QFont.Weight.Bold)
        marked.setForeground(QColor(tokens.PRIMARY))
        for day in busy:
            self.calendar.setDateTextFormat(QDate(day.year, day.month, day.day), marked)
        self._highlighted = busy

    def _load(self, day: date) -> None:
        self.day = day
        overview = day_overview(self._conn, day, include_reports=self._include_reports)
        self._overview = overview
        title = f"{day:%A}, {day.day} {day:%B %Y}"
        self.day_label.setText(f"Today · {title}" if day == local_today() else title)
        visits, registrations, reports = (
            overview["visits"],
            overview["registrations"],
            overview["reports"],
        )
        self.visits_badge.set(f"{len(visits)} visit{'s' if len(visits) != 1 else ''}", "info")
        self.registrations_badge.set(f"{len(registrations)} new", "success")
        self.reports_badge.set(
            f"{len(reports)} report{'s' if len(reports) != 1 else ''}", "neutral"
        )

        self.visits_table.setRowCount(0)
        for row, visit in enumerate(visits):
            self.visits_table.insertRow(row)
            self.visits_table.setItem(
                row, 0, table_item(local_time(visit["created_at"]), muted=True)
            )
            self.visits_table.setItem(row, 1, table_item(f"#{visit['token_num']}"))
            self.visits_table.setCellWidget(
                row, 2, person_cell(visit["full_name"], visit["patient_number"])
            )
            self.visits_table.setItem(row, 3, table_item(visit["dept_name"], muted=True))
            self.visits_table.setCellWidget(row, 4, cell(Badge.for_status(visit["status"])))

        self.registrations_table.setRowCount(0)
        for row, patient in enumerate(registrations):
            self.registrations_table.insertRow(row)
            self.registrations_table.setItem(
                row, 0, table_item(local_time(patient["created_at"]), muted=True)
            )
            self.registrations_table.setCellWidget(
                row, 1, person_cell(patient["full_name"], patient["patient_number"])
            )
            self.registrations_table.setItem(row, 2, table_item(age_sex(patient), muted=True))
            self.registrations_table.setItem(
                row, 3, table_item(patient["contact_no"] or "—", muted=True)
            )

        self.reports_table.setRowCount(0)
        for row, report in enumerate(reports):
            self.reports_table.insertRow(row)
            self.reports_table.setItem(
                row, 0, table_item(local_time(report["created_at"]), muted=True)
            )
            self.reports_table.setItem(row, 1, table_item(report["report_number"], muted=True))
            self.reports_table.setCellWidget(
                row, 2, person_cell(report["full_name"], report["patient_number"])
            )
            self.reports_table.setItem(row, 3, table_item(report["diagnosis"]))
            self.reports_table.setItem(row, 4, table_item(report["doctor_name"], muted=True))

        for page, rows in zip(self._pages, (visits, registrations, reports), strict=True):
            page.setCurrentIndex(0 if rows else 1)

    # Actions --------------------------------------------------------------
    def _open_patient_at(self, table_widget: QTableWidget, row: int) -> None:
        rows = (
            self._overview["visits"]
            if table_widget is self.visits_table
            else self._overview["registrations"]
        )
        if 0 <= row < len(rows):
            self.open_patient.emit(rows[row]["patient_id"])
            self.accept()

    def _view_report(self, row: int) -> None:
        reports = self._overview["reports"]
        if not 0 <= row < len(reports):
            return
        report = reports[row]
        patient = get_patient(self._conn, report["patient_id"])
        ReportViewerDialog(self._conn, report, patient, self).exec()
