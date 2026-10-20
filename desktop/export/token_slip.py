"""Printed token slip handed to the patient at check-in (the design's
"printed token slips" output). Sized for an 80 mm receipt printer; on a
regular printer it prints as a small slip at the top of the page.
"""

from __future__ import annotations

from html import escape

from PyQt6.QtCore import QMarginsF, QSizeF
from PyQt6.QtGui import QFont, QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo

from common import design_tokens as tokens
from common.clock import format_local_datetime
from desktop.export.report_pdf import APP_NAME, PDF_FONT_FAMILIES

SLIP_SIZE_MM = QSizeF(80, 110)


def slip_html(slip: dict) -> str:
    """`slip`: token_num, dept_name, full_name, patient_number, issued_at (UTC ISO)."""
    return f"""
<html><body style="color:{tokens.TEXT_PRIMARY};">
<p align="center" style="font-size:9pt; color:{tokens.TEXT_SECONDARY}; margin:0;">
{APP_NAME}</p>
<p align="center" style="font-size:9pt; font-weight:600; margin-top:6px; margin-bottom:0;">
OPD TOKEN</p>
<p align="center" style="font-size:44pt; font-weight:700; margin:0;">#{slip["token_num"]}</p>
<p align="center" style="font-size:12pt; font-weight:600; margin-top:0;">
{escape(slip["dept_name"])}</p>
<hr>
<p style="font-size:10pt; margin-bottom:2px;">{escape(slip["full_name"])}</p>
<p style="font-size:9pt; color:{tokens.TEXT_SECONDARY}; margin-top:0;">
Patient no. {escape(slip["patient_number"])}<br>
{escape(format_local_datetime(slip["issued_at"]))}</p>
<p align="center" style="font-size:9pt; margin-top:10px;">
Please wait until your token is called.</p>
</body></html>
"""


def print_slip(slip: dict, printer: QPrinter) -> None:
    """Print the slip on `printer` (a real printer, or a PDF in tests)."""
    printer.setPageSize(QPageSize(SLIP_SIZE_MM, QPageSize.Unit.Millimeter, "Token slip"))
    printer.setPageMargins(QMarginsF(4, 4, 4, 4), QPageLayout.Unit.Millimeter)
    document = QTextDocument()
    font = QFont()
    font.setFamilies(PDF_FONT_FAMILIES)
    font.setPointSizeF(10)
    document.setDefaultFont(font)
    document.setHtml(slip_html(slip))
    document.print(printer)


def has_default_printer() -> bool:
    return not QPrinterInfo.defaultPrinter().isNull()
