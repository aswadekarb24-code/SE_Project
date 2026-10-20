"""Receptionist check-in screen: full offline patient intake + queue token
issuance, with keyboard-friendly fields per the UI design doc.
"""

from __future__ import annotations

import re
import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from common.dto import PatientIntake
from desktop.broadcast.broadcaster import Broadcaster
from desktop.services.department_service import list_departments
from desktop.services.queue_service import issue_queue_token

_DOB_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ReceptionWindow(QWidget):
    def __init__(
        self,
        conn: sqlite3.Connection,
        broadcaster: Broadcaster | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._broadcaster = broadcaster

        self.full_name_input = QLineEdit()
        self.dob_input = QLineEdit()
        self.dob_input.setPlaceholderText("YYYY-MM-DD")
        self.gender_input = QLineEdit()
        self.contact_input = QLineEdit()
        self.department_select = QComboBox()
        for dept_id, name in list_departments(conn):
            self.department_select.addItem(name, dept_id)

        self.issue_button = QPushButton("Issue Token")
        self.issue_button.setProperty("variant", "primary")
        self.issue_button.clicked.connect(self._on_issue_token)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Full name*", self.full_name_input)
        form.addRow("Date of birth* (YYYY-MM-DD)", self.dob_input)
        form.addRow("Gender", self.gender_input)
        form.addRow("Contact no.", self.contact_input)
        form.addRow("Department", self.department_select)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(form)
        layout.addWidget(self.issue_button)
        layout.addWidget(self.status_label)

    def _on_issue_token(self) -> None:
        full_name = self.full_name_input.text().strip()
        dob = self.dob_input.text().strip()

        if not full_name or not _DOB_PATTERN.match(dob):
            QMessageBox.warning(
                self,
                "Invalid input",
                "Full name and a valid date of birth (YYYY-MM-DD) are required.",
            )
            return

        patient = PatientIntake(
            full_name=full_name,
            dob=dob,
            gender=self.gender_input.text().strip() or None,
            contact_no=self.contact_input.text().strip() or None,
        )
        department_id = self.department_select.currentData()

        result = issue_queue_token(
            self._conn, patient, department_id, broadcaster=self._broadcaster
        )

        self.status_label.setText(f"Token #{result.token_num} issued ({result.status.value})")
        self.full_name_input.clear()
        self.dob_input.clear()
        self.gender_input.clear()
        self.contact_input.clear()
