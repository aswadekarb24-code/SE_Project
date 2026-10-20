"""Doctor console: call the next patient, write their report, complete the
consultation. Drives the queue-token state machine (WAITING -> CALLED ->
DONE) and broadcasts each transition to LAN display clients.

A consultation in progress is restored from the database, so a doctor who
logs out (or restarts the app) mid-consultation picks up where they left
off.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.auth_service import AuthenticatedUser
from desktop.services.dashboard_service import current_consultation, doctor_summary, todays_queue
from desktop.services.department_service import list_departments
from desktop.services.patient_service import age_sex, get_patient
from desktop.services.queue_service import call_next, complete_token
from desktop.services.report_service import report_count_for_token
from desktop.ui.components import (
    Avatar,
    Badge,
    Card,
    StatCard,
    button,
    cell,
    combo_box,
    empty_state,
    label,
    person_cell,
    table,
    table_item,
)
from desktop.ui.pages.base import Page
from desktop.ui.report_dialogs import ReportEditorDialog, ReportViewerDialog


def _greeting() -> str:
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"


class DoctorConsole(Page):
    title = "Consultations"

    def __init__(
        self,
        conn: sqlite3.Connection,
        user: AuthenticatedUser,
        broadcaster: Broadcaster | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn
        self._user = user
        self._broadcaster = broadcaster
        self._current: dict | None = None
        self._current_token_id: str | None = None
        self.subtitle = f"{_greeting()}, {user.display_name}. Call the next patient when ready."

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        self.waiting_stat = StatCard("Waiting", "clock", "warning")
        self.seen_stat = StatCard("Seen today", "check-circle", "success")
        self.reports_stat = StatCard("My reports today", "file-text", "lavender")
        self.next_stat = StatCard("Next up", "bell", "info")
        stats = QHBoxLayout()
        stats.setSpacing(16)
        for stat in (self.waiting_stat, self.seen_stat, self.reports_stat, self.next_stat):
            stats.addWidget(stat)
        layout.addLayout(stats)

        lower = QHBoxLayout()
        lower.setSpacing(20)

        # Now serving ----------------------------------------------------
        self.department_select = combo_box()
        self.department_select.setFixedWidth(190)
        for dept_id, name in list_departments(conn):
            self.department_select.addItem(name, dept_id)
        if user.dept_id is not None:
            self.department_select.setCurrentIndex(self.department_select.findData(user.dept_id))
        self.department_select.currentIndexChanged.connect(self.refresh)

        serving = Card("Now serving", action=self.department_select)
        self.serving_stack = QStackedWidget()
        self.serving_stack.addWidget(
            empty_state(
                "No patient with you",
                "Call the next waiting patient when you're ready.",
                "stethoscope",
            )
        )
        self.serving_stack.addWidget(self._build_current_panel())
        serving.add(self.serving_stack, 1)

        self.status_label = label("No patient called", "muted")
        serving.add(self.status_label)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.call_next_button = button("Call next", "primary", "bell", tall=True)
        self.call_next_button.clicked.connect(self._on_call_next)
        self.report_button = button("Write report", "secondary", "file-text", tall=True)
        self.report_button.clicked.connect(self._on_write_report)
        self.history_button = button("Patient history", "ghost")
        self.history_button.clicked.connect(self._on_open_history)
        self.complete_button = button("Complete consultation", "secondary", "check", tall=True)
        self.complete_button.clicked.connect(self._on_complete)
        actions.addWidget(self.call_next_button)
        actions.addWidget(self.report_button)
        actions.addWidget(self.history_button)
        actions.addStretch(1)
        actions.addWidget(self.complete_button)
        serving.body.addLayout(actions)
        serving.add(
            label("Shortcuts: F2 call next  ·  F3 write report  ·  F4 complete", "shortcutHint")
        )
        for key, handler, widget in (
            ("F2", self._on_call_next, self.call_next_button),
            ("F3", self._on_write_report, self.report_button),
            ("F4", self._on_complete, self.complete_button),
        ):
            # Same guard as the button: the shortcut does nothing while it's disabled.
            QShortcut(
                QKeySequence(key),
                self,
                activated=lambda h=handler, w=widget: w.isEnabled() and h(),
            )
        lower.addWidget(serving, 5)

        # Queue -------------------------------------------------------------
        self.queue_card = Card("Today's queue")
        self.queue_table = table(["Token", "Patient", "Status"], row_height=56)
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.queue_table.setColumnWidth(0, 72)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.queue_table.setColumnWidth(2, 140)
        self.queue_stack = QStackedWidget()
        self.queue_stack.addWidget(self.queue_table)
        self.queue_stack.addWidget(
            empty_state("Queue is empty", "Patients checked in at reception appear here.", "clock")
        )
        self.queue_card.add(self.queue_stack, 1)
        lower.addWidget(self.queue_card, 4)
        layout.addLayout(lower, 1)

        self._update_buttons()

    def _build_current_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("servingPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(22)
        token_box = QVBoxLayout()
        token_box.setSpacing(0)
        token_box.addStretch(1)
        token_box.addWidget(label("TOKEN", "tokenCaption"))
        self.token_label = label("", "tokenHero")
        token_box.addWidget(self.token_label)
        token_box.addStretch(1)
        layout.addLayout(token_box)

        divider = QFrame()
        divider.setObjectName("vDivider")
        divider.setFixedWidth(1)
        layout.addWidget(divider)

        self.patient_avatar_slot = QHBoxLayout()
        layout.addLayout(self.patient_avatar_slot)
        details = QVBoxLayout()
        details.setSpacing(4)
        self.patient_name_label = label("", "detailName")
        self.patient_meta_label = label("", "muted")
        self.report_badge = Badge("", "neutral")
        details.addStretch(1)
        details.addWidget(self.patient_name_label)
        details.addWidget(self.patient_meta_label)
        details.addSpacing(6)
        details.addWidget(self.report_badge)
        details.addStretch(1)
        layout.addLayout(details, 1)
        return panel

    # State ------------------------------------------------------------
    @property
    def department_id(self) -> int:
        return self.department_select.currentData()

    def refresh(self, *_args) -> None:
        dept_id = self.department_id
        self._current = current_consultation(self._conn, dept_id)
        self._current_token_id = self._current["token_id"] if self._current else None
        self._render_current()

        summary = doctor_summary(self._conn, dept_id, self._user.doctor_id)
        queue = todays_queue(self._conn, dept_id)
        waiting = [token for token in queue if token["status"] == "WAITING"]
        self.waiting_stat.set(summary["waiting"], f"in {self.department_select.currentText()}")
        self.seen_stat.set(summary["seen_today"], "consultations completed")
        self.reports_stat.set(summary["reports_today"], "written by you")
        if waiting:
            self.next_stat.set(f"#{waiting[0]['token_num']}", waiting[0]["full_name"])
        else:
            self.next_stat.set("—", "nobody waiting")

        self.queue_card.title_label.setText(
            f"Today's queue · {self.department_select.currentText()}"
        )
        self.queue_table.setRowCount(0)
        for row, token in enumerate(queue):
            self.queue_table.insertRow(row)
            self.queue_table.setItem(row, 0, table_item(f"#{token['token_num']}"))
            self.queue_table.setCellWidget(
                row, 1, person_cell(token["full_name"], token["patient_number"])
            )
            self.queue_table.setCellWidget(row, 2, cell(Badge.for_status(token["status"])))
            if token["token_id"] == self._current_token_id:
                self.queue_table.selectRow(row)  # highlight the patient being seen
        if self._current_token_id is None:
            self.queue_table.clearSelection()
        self.queue_stack.setCurrentIndex(0 if queue else 1)

    def _render_current(self) -> None:
        current = self._current
        if current is None:
            self.serving_stack.setCurrentIndex(0)
            self._update_buttons()
            return
        patient = get_patient(self._conn, current["patient_id"])
        self.token_label.setText(f"#{current['token_num']}")
        while self.patient_avatar_slot.count():
            old = self.patient_avatar_slot.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        self.patient_avatar_slot.addWidget(Avatar(patient["full_name"], 56))
        self.patient_name_label.setText(patient["full_name"])
        meta = f"{patient['patient_number']}  ·  {age_sex(patient)}"
        if patient["contact_no"]:
            meta += f"  ·  {patient['contact_no']}"
        self.patient_meta_label.setText(meta)
        reports = report_count_for_token(self._conn, current["token_id"])
        if reports:
            self.report_badge.set("Report saved", "success")
        else:
            self.report_badge.set("No report yet", "warning")
        self.serving_stack.setCurrentIndex(1)
        self._update_buttons()

    def _update_buttons(self) -> None:
        busy = self._current_token_id is not None
        self.call_next_button.setEnabled(not busy)
        self.call_next_button.setToolTip(
            "Complete the current consultation first."
            if busy
            else "Call the next waiting patient (F2)"
        )
        self.report_button.setToolTip("Write a report for this patient (F3)")
        self.complete_button.setToolTip("Complete this consultation (F4)")
        for widget in (self.report_button, self.history_button, self.complete_button):
            widget.setEnabled(busy)

    # Actions ----------------------------------------------------------
    def _on_call_next(self) -> None:
        result = call_next(self._conn, self.department_id, broadcaster=self._broadcaster)
        self.refresh()
        if result is None:
            self.status_label.setText("Queue is empty for this department")
            return
        self.status_label.setText(f"Now serving token #{result.token_num} ({result.status.value})")

    def _on_complete(self) -> None:
        if self._current_token_id is None:
            return
        result = complete_token(self._conn, self._current_token_id, broadcaster=self._broadcaster)
        self._current_token_id = None
        self.refresh()
        self.status_label.setText(f"Token #{result.token_num} complete ({result.status.value})")

    def _on_write_report(self) -> None:
        if self._current is None:
            return
        patient = get_patient(self._conn, self._current["patient_id"])
        dialog = ReportEditorDialog(
            self._conn, self._user, patient, token_id=self._current["token_id"], parent=self
        )
        if dialog.exec() and dialog.saved_report:
            self._render_current()
            ReportViewerDialog(
                self._conn, dialog.saved_report, patient, self, just_saved=True
            ).exec()

    def _on_open_history(self) -> None:
        if self._current is not None:
            self.navigate.emit("patients", self._current["patient_id"])
