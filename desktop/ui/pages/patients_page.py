"""Patient directory with a detail panel. Everyone sees demographics and
the visit history; doctors also see the patient's medical reports and can
write a new one or export any of them as PDF. Receptionists never see
clinical content.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from common.clock import format_date, format_local_datetime
from desktop.services.auth_service import AuthenticatedUser, Role
from desktop.services.patient_service import age_sex, get_patient, list_visits, search_patients
from desktop.services.report_service import list_reports
from desktop.ui.components import (
    Avatar,
    Badge,
    Card,
    Segmented,
    button,
    cell,
    empty_state,
    label,
    person_cell,
    search_field,
    table,
    table_item,
)
from desktop.ui.pages.base import Page
from desktop.ui.report_dialogs import ReportEditorDialog, ReportViewerDialog, export_with_dialog

SEARCH_LIMIT = 200


class PatientsPage(Page):
    title = "Patients"
    subtitle = "Search by patient number, name or phone."

    def __init__(self, conn: sqlite3.Connection, user: AuthenticatedUser) -> None:
        super().__init__()
        self._conn = conn
        self._user = user
        self._is_doctor = user.role == Role.DOCTOR
        self._patient: dict | None = None
        self._reports: list[dict] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Directory ------------------------------------------------------
        self.count_badge = Badge("", "neutral")
        directory = Card("All patients", action=self.count_badge)
        self.search_input = search_field("Search by patient no., name or phone")
        self.search_input.textChanged.connect(self.refresh)
        directory.add(self.search_input)
        self.table = table(["Patient", "Age · Sex", "Phone", "Registered"], row_height=58)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 120), (2, 150), (3, 130)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.directory_stack = QStackedWidget()
        self.directory_stack.addWidget(self.table)
        self.directory_stack.addWidget(
            empty_state("No patients found", "Check the spelling or search by phone.", "users")
        )
        directory.add(self.directory_stack, 1)
        layout.addWidget(directory, 3)

        # Detail ---------------------------------------------------------
        detail_card = Card(padding=22)
        detail_card.setMinimumWidth(420)
        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(
            empty_state(
                "Select a patient",
                "Their details and history will appear here.",
                "users",
            )
        )
        self.detail_stack.addWidget(self._build_detail())
        detail_card.add(self.detail_stack, 1)
        layout.addWidget(detail_card, 2)

    # Building -----------------------------------------------------------
    def _build_detail(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.header_row = QHBoxLayout()
        self.header_row.setSpacing(14)
        layout.addLayout(self.header_row)

        info = QGridLayout()
        info.setHorizontalSpacing(18)
        info.setVerticalSpacing(10)
        self.info_values: dict[str, object] = {}
        for index, key in enumerate(("Date of birth", "Age · Sex", "Phone", "Registered")):
            info.addWidget(label(key, "fieldLabel"), (index // 2) * 2, index % 2)
            value = label("", "infoValue")
            info.addWidget(value, (index // 2) * 2 + 1, index % 2)
            self.info_values[key] = value
        layout.addLayout(info)

        self.visits_table = table(["Date", "Department", "Token", "Status"], row_height=48)
        visits_header = self.visits_table.horizontalHeader()
        for column, width in ((0, 115), (2, 70), (3, 125)):
            visits_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.visits_table.setColumnWidth(column, width)
        self.visits_empty = label("No visits yet.", "muted")

        visits_box = QWidget()
        visits_layout = QVBoxLayout(visits_box)
        visits_layout.setContentsMargins(0, 0, 0, 0)
        visits_layout.addWidget(self.visits_table, 1)
        visits_layout.addWidget(self.visits_empty)

        if not self._is_doctor:
            layout.addWidget(label("Visits", "sectionLabel"))
            layout.addWidget(visits_box, 1)
            return panel

        self.history_tabs = Segmented(["Medical reports", "Visits"])
        layout.addWidget(self.history_tabs)
        self.history_stack = QStackedWidget()
        layout.addWidget(self.history_stack, 1)

        reports_box = QWidget()
        reports_layout = QVBoxLayout(reports_box)
        reports_layout.setContentsMargins(0, 0, 0, 0)
        reports_layout.setSpacing(12)
        self.reports_table = table(["Date", "Diagnosis", "Doctor"], row_height=48)
        self.reports_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.reports_table.setColumnWidth(0, 115)
        self.reports_table.itemSelectionChanged.connect(self._update_report_buttons)
        self.reports_table.doubleClicked.connect(self._view_report)
        self.reports_empty = label("No reports yet. Write the first one.", "muted")
        reports_layout.addWidget(self.reports_table, 1)
        reports_layout.addWidget(self.reports_empty)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.new_report_button = button("New report", "primary", "plus")
        self.new_report_button.clicked.connect(self._new_report)
        self.view_report_button = button("View")
        self.view_report_button.clicked.connect(self._view_report)
        self.export_report_button = button("Export PDF", "secondary", "download")
        self.export_report_button.clicked.connect(self._export_report)
        actions.addWidget(self.new_report_button)
        actions.addStretch(1)
        actions.addWidget(self.view_report_button)
        actions.addWidget(self.export_report_button)
        reports_layout.addLayout(actions)

        self.history_stack.addWidget(reports_box)
        self.history_stack.addWidget(visits_box)
        for index, option in enumerate(self.history_tabs.buttons):
            option.toggled.connect(
                lambda checked, i=index: checked and self.history_stack.setCurrentIndex(i)
            )
        return panel

    # Data ---------------------------------------------------------------
    def refresh(self) -> None:
        selected_id = self._patient["patient_id"] if self._patient else None
        patients = search_patients(self._conn, self.search_input.text(), SEARCH_LIMIT)
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row, patient in enumerate(patients):
            self.table.insertRow(row)
            name_item = table_item("", data=patient["patient_id"])
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(
                row, 0, person_cell(patient["full_name"], patient["patient_number"])
            )
            self.table.setItem(row, 1, table_item(age_sex(patient), muted=True))
            self.table.setItem(row, 2, table_item(patient["contact_no"] or "—", muted=True))
            registered = format_date(patient["created_at"][:10])
            self.table.setItem(row, 3, table_item(registered, muted=True))
            if patient["patient_id"] == selected_id:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        self.directory_stack.setCurrentIndex(0 if patients else 1)
        total = len(patients)
        suffix = "+" if total == SEARCH_LIMIT else ""
        self.count_badge.set(f"{total}{suffix} shown", "neutral")
        if selected_id:
            self._show_patient(selected_id)

    def focus_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    def select_patient(self, patient_id: str) -> None:
        """Open a patient's details (used when another page links here)."""
        patient = get_patient(self._conn, patient_id)
        if patient is None:
            return
        self._patient = patient
        self.search_input.blockSignals(True)
        self.search_input.setText(patient["patient_number"])
        self.search_input.blockSignals(False)
        self.refresh()

    def _on_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        patient_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        self._show_patient(patient_id)

    def _show_patient(self, patient_id: str) -> None:
        patient = get_patient(self._conn, patient_id)
        if patient is None:
            self._patient = None
            self.detail_stack.setCurrentIndex(0)
            return
        self._patient = patient

        while self.header_row.count():
            item = self.header_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.header_row.addWidget(Avatar(patient["full_name"], 56))
        names = QVBoxLayout()
        names.setSpacing(4)
        names.addWidget(label(patient["full_name"], "detailName"))
        names.addWidget(Badge(patient["patient_number"], "info"), 0, Qt.AlignmentFlag.AlignLeft)
        holder = QWidget()
        holder.setLayout(names)
        self.header_row.addWidget(holder, 1)

        self.info_values["Date of birth"].setText(format_date(patient["dob"]))
        self.info_values["Age · Sex"].setText(age_sex(patient))
        self.info_values["Phone"].setText(patient["contact_no"] or "—")
        self.info_values["Registered"].setText(format_local_datetime(patient["created_at"]))

        visits = list_visits(self._conn, patient_id)
        self.visits_table.setRowCount(0)
        for row, visit in enumerate(visits):
            self.visits_table.insertRow(row)
            self.visits_table.setItem(row, 0, table_item(format_date(visit["issued_date"])))
            self.visits_table.setItem(row, 1, table_item(visit["dept_name"], muted=True))
            self.visits_table.setItem(row, 2, table_item(f"#{visit['token_num']}", muted=True))
            self.visits_table.setCellWidget(row, 3, cell(Badge.for_status(visit["status"])))
        self.visits_table.setVisible(bool(visits))
        self.visits_empty.setVisible(not visits)

        if self._is_doctor:
            self._reports = list_reports(self._conn, patient_id)
            self.reports_table.setRowCount(0)
            for row, report in enumerate(self._reports):
                self.reports_table.insertRow(row)
                self.reports_table.setItem(
                    row, 0, table_item(format_date(report["visit_date"]), data=report["report_id"])
                )
                self.reports_table.setItem(row, 1, table_item(report["diagnosis"]))
                self.reports_table.setItem(row, 2, table_item(report["doctor_name"], muted=True))
            self.reports_table.setVisible(bool(self._reports))
            self.reports_empty.setVisible(not self._reports)
            if self._reports:
                self.reports_table.selectRow(0)
            self._update_report_buttons()

        self.detail_stack.setCurrentIndex(1)

    # Reports ------------------------------------------------------------
    def _selected_report(self) -> dict | None:
        rows = self.reports_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._reports[rows[0].row()]

    def _update_report_buttons(self) -> None:
        has_selection = self._selected_report() is not None
        self.view_report_button.setEnabled(has_selection)
        self.export_report_button.setEnabled(has_selection)

    def _new_report(self) -> None:
        if self._patient is None:
            return
        dialog = ReportEditorDialog(self._conn, self._user, self._patient, parent=self)
        if dialog.exec() and dialog.saved_report:
            self._show_patient(self._patient["patient_id"])
            ReportViewerDialog(
                self._conn, dialog.saved_report, self._patient, self, just_saved=True
            ).exec()

    def _view_report(self, *_args) -> None:
        report = self._selected_report()
        if report is not None and self._patient is not None:
            ReportViewerDialog(self._conn, report, self._patient, self).exec()

    def _export_report(self) -> None:
        report = self._selected_report()
        if report is not None and self._patient is not None:
            export_with_dialog(self, self._conn, report, self._patient)
