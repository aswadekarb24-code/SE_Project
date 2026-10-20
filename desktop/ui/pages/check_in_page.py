"""Receptionist check-in: register a new patient, or find a returning one,
and issue a queue token. Returning patients are checked in against their
existing record, so their visits and reports stay in one history.

Keyboard-first: Enter in the new-patient form registers; Enter in the
returning-patient search issues a token for the selected (or only) match;
Ctrl+P prints the last token slip. Slips can also print automatically on
the default printer after every token.
"""

from __future__ import annotations

import sqlite3

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from common.clock import now_iso
from common.dto import PatientIntake, QueueTokenIssued
from desktop.broadcast.broadcaster import Broadcaster
from desktop.data.settings import AUTO_PRINT_SLIPS, get_flag, set_flag
from desktop.export.token_slip import has_default_printer, print_slip
from desktop.services.auth_service import AuthenticatedUser
from desktop.services.department_service import list_departments
from desktop.services.patient_service import (
    GENDERS,
    PatientValidationError,
    age_sex,
    search_patients,
)
from desktop.services.queue_service import issue_queue_token
from desktop.ui.components import (
    Card,
    button,
    combo_box,
    field,
    label,
    line_edit,
    person_cell,
    search_field,
)
from desktop.ui.pages.base import Page

RECENT_LIMIT = 30


class CheckInPage(Page):
    title = "Patient check-in"
    subtitle = "Register new patients or check in returning ones."

    def __init__(
        self,
        conn: sqlite3.Connection,
        user: AuthenticatedUser,
        broadcaster: Broadcaster | None = None,
    ) -> None:
        super().__init__()
        self._conn = conn
        self._broadcaster = broadcaster
        self.last_slip: dict | None = None
        departments = list_departments(conn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        cards = QHBoxLayout()
        cards.setSpacing(20)

        # New patient ---------------------------------------------------
        new_card = Card("New patient")
        self.full_name_input = line_edit("e.g. Jane Doe")
        self.dob_input = line_edit("YYYY-MM-DD")
        self.gender_input = combo_box()
        self.gender_input.addItem("Not specified", None)
        for gender in GENDERS:
            self.gender_input.addItem(gender, gender)
        self.contact_input = line_edit("e.g. +91 98765 43210")
        self.department_select = combo_box()
        for dept_id, name in departments:
            self.department_select.addItem(name, dept_id)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.addWidget(field("Full name *", self.full_name_input), 0, 0, 1, 2)
        grid.addWidget(field("Date of birth *", self.dob_input), 1, 0)
        grid.addWidget(field("Gender", self.gender_input), 1, 1)
        grid.addWidget(field("Contact no.", self.contact_input), 2, 0)
        grid.addWidget(field("Department", self.department_select), 2, 1)
        new_card.body.addLayout(grid)

        self.form_error = label("", "errorLabel", wrap=True)
        self.form_error.hide()
        new_card.add(self.form_error)
        new_card.body.addStretch(1)
        self.issue_button = button("Register and issue token", "primary", "user-plus", tall=True)
        self.issue_button.setToolTip("Register and issue token (Enter)")
        self.issue_button.clicked.connect(self._on_issue_token)
        new_card.add(self.issue_button)
        cards.addWidget(new_card, 3)
        for field_widget in (self.full_name_input, self.dob_input, self.contact_input):
            field_widget.returnPressed.connect(self._on_issue_token)

        # Returning patient ---------------------------------------------
        returning_card = Card("Returning patient")
        self.search_input = search_field("Patient no., name or phone")
        self.search_input.textChanged.connect(self._search)
        self.search_input.returnPressed.connect(self._on_search_enter)
        returning_card.add(self.search_input)
        self.results = QListWidget()
        self.results.setObjectName("resultsList")
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.currentItemChanged.connect(self._update_returning_button)
        self.results.itemActivated.connect(lambda _item: self._on_issue_returning())
        returning_card.add(self.results, 1)
        self.results_hint = label("", "muted")
        returning_card.add(self.results_hint)
        self.returning_department = combo_box()
        for dept_id, name in departments:
            self.returning_department.addItem(name, dept_id)
        returning_card.add(field("Department", self.returning_department))
        self.returning_button = button("Issue token", "primary", "arrow-right", tall=True)
        self.returning_button.clicked.connect(self._on_issue_returning)
        returning_card.add(self.returning_button)
        cards.addWidget(returning_card, 2)
        layout.addLayout(cards, 1)

        # Printing preference --------------------------------------------
        self.auto_print_check = QCheckBox("Print a token slip automatically after issuing")
        self.auto_print_check.setChecked(get_flag(conn, AUTO_PRINT_SLIPS))
        self.auto_print_check.toggled.connect(lambda on: set_flag(conn, AUTO_PRINT_SLIPS, on))
        layout.addWidget(self.auto_print_check)

        # Result banner -------------------------------------------------
        self.banner = QFrame()
        self.banner.setObjectName("tokenBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(22, 16, 22, 16)
        banner_layout.setSpacing(18)
        self.token_label = label("", "tokenNumber")
        banner_layout.addWidget(self.token_label)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.status_label = label("", "bannerTitle")
        self.banner_detail = label("", "bannerText")
        text.addWidget(self.status_label)
        text.addWidget(self.banner_detail)
        banner_layout.addLayout(text, 1)
        self.print_button = button("Print slip", "secondary", "printer")
        self.print_button.setToolTip("Print token slip (Ctrl+P)")
        self.print_button.clicked.connect(self.print_last_slip)
        banner_layout.addWidget(self.print_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.banner.hide()
        layout.addWidget(self.banner)

        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.print_last_slip)

        self._search()

    def refresh(self) -> None:
        self._search()

    def focus_new_patient(self) -> None:
        self.full_name_input.setFocus()

    def focus_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    # New patient --------------------------------------------------------
    def _on_issue_token(self) -> None:
        intake = PatientIntake(
            full_name=self.full_name_input.text(),
            dob=self.dob_input.text(),
            gender=self.gender_input.currentData(),
            contact_no=self.contact_input.text(),
        )
        try:
            result = issue_queue_token(
                self._conn,
                intake,
                self.department_select.currentData(),
                broadcaster=self._broadcaster,
            )
        except PatientValidationError as error:
            self.form_error.setText(str(error))
            self.form_error.show()
            return

        self.form_error.hide()
        name = " ".join(intake.full_name.split())
        self._show_result(result, name, self.department_select.currentText())
        for widget in (self.full_name_input, self.dob_input, self.contact_input):
            widget.clear()
        self.gender_input.setCurrentIndex(0)
        self.full_name_input.setFocus()
        self._search()

    # Returning patient --------------------------------------------------
    def _search(self) -> None:
        query = self.search_input.text().strip()
        patients = search_patients(self._conn, query, limit=RECENT_LIMIT)
        self.results.clear()
        for patient in patients:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, patient)
            detail = f"{patient['patient_number']}  ·  {age_sex(patient)}"
            if patient["contact_no"]:
                detail += f"  ·  {patient['contact_no']}"
            row = person_cell(patient["full_name"], detail)
            item.setSizeHint(QSize(0, 58))
            self.results.addItem(item)
            self.results.setItemWidget(item, row)
        if query:
            self.results_hint.setText("No matching patients." if not patients else "")
        else:
            self.results_hint.setText(
                "Recently registered patients. Type to search everyone."
                if patients
                else "No patients registered yet."
            )
        self.results_hint.setVisible(bool(self.results_hint.text()))
        self._update_returning_button()

    def _update_returning_button(self, *_args) -> None:
        self.returning_button.setEnabled(self.results.currentItem() is not None)

    def _on_search_enter(self) -> None:
        """Enter in the search box: issue for the selected match, or for the
        only match when the search narrowed it down to one patient.
        """
        if self.results.currentItem() is None and self.results.count() == 1:
            self.results.setCurrentRow(0)
        if self.results.currentItem() is not None:
            self._on_issue_returning()

    def _on_issue_returning(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        patient = item.data(Qt.ItemDataRole.UserRole)
        result = issue_queue_token(
            self._conn,
            PatientIntake(
                full_name=patient["full_name"],
                dob=patient["dob"],
                gender=patient["gender"],
                contact_no=patient["contact_no"],
                patient_id=patient["patient_id"],
            ),
            self.returning_department.currentData(),
            broadcaster=self._broadcaster,
        )
        self._show_result(result, patient["full_name"], self.returning_department.currentText())
        self.search_input.clear()

    # Result and slip ----------------------------------------------------
    def _show_result(self, result: QueueTokenIssued, name: str, department: str) -> None:
        self.last_slip = {
            "token_num": result.token_num,
            "dept_name": department,
            "full_name": name,
            "patient_number": result.patient_number,
            "issued_at": now_iso(),
        }
        self.token_label.setText(f"#{result.token_num}")
        self.status_label.setText(f"Token #{result.token_num} issued to {name}")
        self.banner_detail.setText(
            f"Patient no. {result.patient_number}  ·  {department}  ·  Please wait to be called."
        )
        self.banner.show()
        if self.auto_print_check.isChecked():
            self._auto_print()

    def _auto_print(self) -> None:
        if not has_default_printer():
            self.banner_detail.setText(
                self.banner_detail.text() + "  ·  No default printer, so the slip wasn't printed."
            )
            return
        print_slip(self.last_slip, QPrinter())

    def print_last_slip(self) -> None:
        """Print the last token's slip, choosing the printer in a dialog."""
        if self.last_slip is None:
            return
        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print token slip")
        if dialog.exec():
            print_slip(self.last_slip, printer)
