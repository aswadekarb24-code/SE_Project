"""Render a medical report to an A4 PDF using Qt's own text engine
(QTextDocument + QPdfWriter): no extra dependency, works fully offline and
inside the PyInstaller build. Every user-entered value is HTML-escaped
before it goes into the document.
"""

from __future__ import annotations

import os
import re
from datetime import date
from html import escape
from pathlib import Path

from PyQt6.QtCore import QMarginsF
from PyQt6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument

from common import design_tokens as tokens
from common.clock import format_date, format_local_datetime, now_iso
from desktop.services.patient_service import age_sex

APP_NAME = "Hybrid Offline-First HMS"

# Static (non-variable) fonts: Qt embeds variable fonts like Segoe UI
# Variable at a heavy default weight, which made every line print bold.
PDF_FONT_FAMILIES = ["Segoe UI", "Arial", "Helvetica", "DejaVu Sans"]


def _text(value: str | None) -> str:
    """Escaped, with line breaks kept; an em dash when empty."""
    if not value:
        return f'<span style="color:{tokens.TEXT_SECONDARY}">—</span>'
    return escape(value).replace("\n", "<br>")


def _vital(label: str, value: str | None, unit: str = "") -> str:
    shown = "—"
    if value:
        # Small unit after a non-breaking space, so "118/76 mmHg" fits one line.
        unit_html = (
            f'<span style="font-size:8pt; color:{tokens.TEXT_SECONDARY};">&nbsp;{unit}</span>'
            if unit
            else ""
        )
        shown = f"{escape(value)}{unit_html}"
    return (
        f'<td width="20%" style="background-color:{tokens.SURFACE_SUBTLE}; padding:8px;">'
        f'<span style="color:{tokens.TEXT_SECONDARY}; font-size:8pt;">{label}</span><br>'
        f'<span style="font-size:11pt;">{shown}</span></td>'
    )


def _section(title: str, body: str | None) -> str:
    return (
        f'<p style="margin-top:14px; margin-bottom:4px; color:{tokens.PRIMARY};'
        f' font-size:9pt; font-weight:600;">{title.upper()}</p>'
        f'<p style="margin-top:0; font-size:10.5pt;">{_text(body)}</p>'
    )


def report_html(report: dict, patient: dict, department: str | None = None) -> str:
    visit_day = date.fromisoformat(report["visit_date"])
    info_rows = [
        ("Patient", escape(patient["full_name"]), "Patient no.", escape(patient["patient_number"])),
        (
            "Age · Sex",
            escape(age_sex(patient, visit_day)),
            "Date of birth",
            escape(format_date(patient["dob"])),
        ),
        (
            "Doctor",
            escape(report["doctor_name"]),
            "Department",
            escape(department) if department else "—",
        ),
        (
            "Contact",
            escape(patient["contact_no"]) if patient.get("contact_no") else "—",
            "Visit date",
            escape(format_date(report["visit_date"])),
        ),
    ]
    info = "".join(
        f'<tr><td width="18%" style="color:{tokens.TEXT_SECONDARY};">{a}</td>'
        f'<td width="32%">{b}</td>'
        f'<td width="18%" style="color:{tokens.TEXT_SECONDARY};">{c}</td>'
        f'<td width="32%">{d}</td></tr>'
        for a, b, c, d in info_rows
    )
    vitals = "".join(
        [
            _vital("Blood pressure", report["blood_pressure"], "mmHg"),
            _vital("Pulse", report["pulse_rate"], "bpm"),
            _vital("Temperature", report["temperature"]),
            _vital("Weight", report["weight"], "kg"),
            _vital("SpO₂", report["spo2"], "%"),
        ]
    )
    follow_up = format_date(report["follow_up_date"]) if report["follow_up_date"] else None

    return f"""
<html><body style="color:{tokens.TEXT_PRIMARY};">
<table width="100%" cellspacing="0" cellpadding="0"><tr>
  <td>
    <span style="font-size:16pt; font-weight:600; color:{tokens.PRIMARY};">{APP_NAME}</span><br>
    <span style="font-size:10pt; color:{tokens.TEXT_SECONDARY};">Medical consultation report</span>
  </td>
  <td align="right" style="font-size:9pt; color:{tokens.TEXT_SECONDARY};">
    Report no. <b style="color:{tokens.TEXT_PRIMARY};">{escape(report["report_number"])}</b><br>
    Recorded {escape(format_local_datetime(report["created_at"]))}
  </td>
</tr></table>
<hr>
<table width="100%" cellspacing="0" cellpadding="5" style="font-size:10pt;">{info}</table>
<p style="margin-top:14px; margin-bottom:6px; color:{tokens.PRIMARY};
   font-size:9pt; font-weight:600;">VITALS</p>
<table width="100%" cellspacing="4" cellpadding="0"><tr>{vitals}</tr></table>
{_section("Chief complaint", report["chief_complaint"])}
{_section("Diagnosis", report["diagnosis"])}
{_section("Prescription", report["prescription"])}
{_section("Advice", report["advice"])}
{_section("Follow-up", follow_up)}
<p style="margin-top:36px; font-size:10pt;">{escape(report["doctor_name"])}<br>
<span style="color:{tokens.TEXT_SECONDARY}; font-size:9pt;">Electronically recorded.
Generated {escape(format_local_datetime(now_iso()))} by {APP_NAME}.</span></p>
</body></html>
"""


def suggested_filename(report: dict, patient: dict) -> str:
    """e.g. "RPT-K7Q2-00007 Jane Doe.pdf", with characters Windows forbids
    in file names removed.
    """
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", patient["full_name"]).strip() or "patient"
    return f"{report['report_number']} {name}.pdf"


def export_report_pdf(
    report: dict, patient: dict, path: Path | str, department: str | None = None
) -> Path:
    """Write the report as an A4 PDF to `path`. Raises OSError if the file
    couldn't be written (e.g. no permission, or the folder doesn't exist).
    """
    path = Path(path)
    if not path.parent.is_dir():
        raise OSError(f"Folder not found: {path.parent}")

    # Write to a temporary file first, then move it into place: QPdfWriter
    # fails silently, and on Windows a PDF that's open in a viewer is
    # locked, so the final replace is what surfaces that as a real error
    # instead of leaving the old file there looking like a success.
    partial = path.with_name(path.name + ".part")
    try:
        _write_pdf(report, patient, partial, department)
        if not partial.is_file() or partial.stat().st_size == 0:
            raise OSError(f"Couldn't write {path}")
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def _write_pdf(report: dict, patient: dict, path: Path, department: str | None) -> None:
    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(16, 16, 16, 16), QPageLayout.Unit.Millimeter)
    writer.setTitle(f"Medical report {report['report_number']}")
    writer.setCreator(APP_NAME)

    document = QTextDocument()
    font = QFont()
    font.setFamilies(PDF_FONT_FAMILIES)
    font.setPointSizeF(10.5)
    document.setDefaultFont(font)
    document.setHtml(report_html(report, patient, department))
    document.print(writer)
    del writer  # finishes and closes the file
