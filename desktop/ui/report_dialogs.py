"""Dialogs for writing a consultation report and for reading / exporting a
saved one. The viewer renders the same HTML the PDF is printed from, so
what the doctor sees is exactly what gets exported.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from common.clock import format_date, local_today
from desktop.export.report_pdf import export_report_pdf, report_html, suggested_filename
from desktop.services.auth_service import AuthenticatedUser
from desktop.services.department_service import list_departments
from desktop.services.patient_service import age_sex
from desktop.services.report_service import ReportDraft, ReportValidationError, create_report
from desktop.ui.components import Avatar, button, field, label, line_edit

_last_export_dir: str | None = None


def department_name(conn: sqlite3.Connection, dept_id: int | None) -> str | None:
    return dict(list_departments(conn)).get(dept_id)


def _text_box(placeholder: str, height: int) -> QPlainTextEdit:
    box = QPlainTextEdit()
    box.setPlaceholderText(placeholder)
    box.setFixedHeight(height)
    box.setTabChangesFocus(True)
    return box


def _patient_header(patient: dict, right: QWidget | None = None) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(Avatar(patient["full_name"], 48))
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(label(patient["full_name"], "dialogTitle"))
    text.addWidget(label(f"{patient['patient_number']}  ·  {age_sex(patient)}", "muted"))
    row.addLayout(text)
    row.addStretch(1)
    if right is not None:
        row.addWidget(right)
    return row


class ReportEditorDialog(QDialog):
    """Write a new report for `patient`. After exec() returns Accepted,
    `saved_report` holds the stored report.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        author: AuthenticatedUser,
        patient: dict,
        token_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"New report: {patient['full_name']}")
        self.setModal(True)
        self.setMinimumWidth(860)
        self._conn = conn
        self._author = author
        self._patient = patient
        self._token_id = token_id
        self.saved_report: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        today = label(
            f"{author.display_name}  ·  {format_date(local_today().isoformat())}", "muted"
        )
        layout.addLayout(_patient_header(patient, today))

        self.complaint_input = _text_box("What brings the patient in today?", 76)
        self.diagnosis_input = line_edit("e.g. Acute viral fever")
        self.bp_input = line_edit("120/80")
        self.pulse_input = line_edit("bpm")
        self.temperature_input = line_edit("°C or °F")
        self.weight_input = line_edit("kg")
        self.spo2_input = line_edit("%")
        self.prescription_input = _text_box(
            "One medicine per line, e.g.\nParacetamol 650 mg - 1 tab three times a day x 3 days",
            150,
        )
        self.advice_input = _text_box("Diet, rest, warning signs to watch for...", 76)
        self.follow_up_input = line_edit("YYYY-MM-DD (optional)")

        columns = QHBoxLayout()
        columns.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(field("Chief complaint *", self.complaint_input))
        vitals = QGridLayout()
        vitals.setHorizontalSpacing(10)
        vitals.setVerticalSpacing(10)
        for column, (caption, widget) in enumerate(
            (
                ("Blood pressure", self.bp_input),
                ("Pulse", self.pulse_input),
                ("Temperature", self.temperature_input),
            )
        ):
            vitals.addWidget(field(caption, widget), 0, column)
        vitals.addWidget(field("Weight", self.weight_input), 1, 0)
        vitals.addWidget(field("SpO₂", self.spo2_input), 1, 1)
        left.addWidget(label("Vitals", "sectionLabel"))
        left.addLayout(vitals)
        left.addWidget(field("Diagnosis *", self.diagnosis_input))
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(field("Prescription", self.prescription_input))
        right.addWidget(field("Advice", self.advice_input))
        right.addWidget(field("Follow-up date", self.follow_up_input))
        right.addStretch(1)

        columns.addLayout(left, 1)
        columns.addLayout(right, 1)
        layout.addLayout(columns)

        self.error_label = label("", "errorLabel", wrap=True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        footer = QHBoxLayout()
        footer.addWidget(
            label(
                "Saved reports can't be edited; they become part of the patient's history.", "muted"
            )
        )
        footer.addStretch(1)
        cancel = button("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_button = button("Save report", "primary", "check")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)
        self.save_button.setToolTip("Save report (Ctrl+S)")
        footer.addWidget(cancel)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        for keys in ("Ctrl+S", "Ctrl+Return"):
            QShortcut(QKeySequence(keys), self, activated=self.save)
        self.complaint_input.setFocus()

    def draft(self) -> ReportDraft:
        return ReportDraft(
            chief_complaint=self.complaint_input.toPlainText(),
            diagnosis=self.diagnosis_input.text(),
            blood_pressure=self.bp_input.text(),
            pulse_rate=self.pulse_input.text(),
            temperature=self.temperature_input.text(),
            weight=self.weight_input.text(),
            spo2=self.spo2_input.text(),
            prescription=self.prescription_input.toPlainText(),
            advice=self.advice_input.toPlainText(),
            follow_up_date=self.follow_up_input.text(),
        )

    def save(self) -> None:
        try:
            self.saved_report = create_report(
                self._conn,
                author=self._author,
                patient_id=self._patient["patient_id"],
                token_id=self._token_id,
                draft=self.draft(),
            )
        except ReportValidationError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        self.accept()


def export_with_dialog(
    parent: QWidget, conn: sqlite3.Connection, report: dict, patient: dict
) -> Path | None:
    """Ask where to save, export the PDF, and return its path (None if the
    user cancelled). Shows an error message if writing fails.
    """
    global _last_export_dir
    folder = _last_export_dir or QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    chosen, _filter = QFileDialog.getSaveFileName(
        parent,
        "Export report as PDF",
        str(Path(folder) / suggested_filename(report, patient)),
        "PDF documents (*.pdf)",
    )
    if not chosen:
        return None
    path = Path(chosen)
    if path.suffix.lower() != ".pdf":
        path = path.with_name(path.name + ".pdf")
    try:
        export_report_pdf(report, patient, path, department_name(conn, report["dept_id"]))
    except OSError as error:
        QMessageBox.warning(
            parent,
            "Export failed",
            f"Couldn't save the PDF.\n\n{error}\n\n"
            "If the file is open in another program, close it and try again.",
        )
        return None
    _last_export_dir = str(path.parent)
    return path


class ReportViewerDialog(QDialog):
    """Read-only view of a saved report with PDF export."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        report: dict,
        patient: dict,
        parent: QWidget | None = None,
        *,
        just_saved: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Report {report['report_number']}")
        self.setModal(True)
        self.resize(760, 720)
        self._conn = conn
        self._report = report
        self._patient = patient

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        if just_saved:
            banner = label(
                f"Report {report['report_number']} saved to the patient's history.", "successBanner"
            )
            layout.addWidget(banner)

        self.preview = QTextBrowser()
        self.preview.setObjectName("reportPreview")
        self.preview.setOpenLinks(False)
        self.preview.setHtml(report_html(report, patient, department_name(conn, report["dept_id"])))
        layout.addWidget(self.preview, 1)

        self.status_label = label("", "muted", wrap=True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        footer = QHBoxLayout()
        self.open_button = button("Open PDF", "ghost")
        self.open_button.hide()
        footer.addWidget(self.open_button)
        footer.addStretch(1)
        close = button("Close")
        close.clicked.connect(self.accept)
        self.export_button = button("Export PDF", "primary", "download")
        self.export_button.clicked.connect(self.export)
        footer.addWidget(close)
        footer.addWidget(self.export_button)
        layout.addLayout(footer)
        self.exported_path: Path | None = None

    def export(self) -> None:
        path = export_with_dialog(self, self._conn, self._report, self._patient)
        if path is None:
            return
        self.exported_path = path
        self.status_label.setText(f"Saved to {path}")
        self.status_label.show()
        self.open_button.show()
        try:
            self.open_button.clicked.disconnect()
        except TypeError:
            pass  # nothing connected yet
        self.open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        )
