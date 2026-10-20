"""Consultation reports: a doctor writes one for a patient, usually during a
queue visit. Reports are append-only -- once saved they're never edited or
deleted, so the patient's medical history stays exactly as it was signed.
A correction is simply a new report.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from common.clock import local_today
from desktop.data.numbering import next_report_number
from desktop.data.repositories.medical_reports_repo import MedicalReportsRepository
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository
from desktop.services.auth_service import AuthenticatedUser, Role

MAX_SHORT_TEXT = 500
MAX_LONG_TEXT = 4000

_BP_PATTERN = re.compile(r"^(\d{2,3})\s*/\s*(\d{2,3})$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ReportValidationError(ValueError):
    """Report input that can't be saved; the message is user-facing."""


@dataclass(frozen=True, slots=True)
class ReportDraft:
    """What the doctor typed. Every field is free text from the form; the
    service validates and normalises it. Blank optional fields are fine.
    """

    chief_complaint: str
    diagnosis: str
    blood_pressure: str = ""
    pulse_rate: str = ""
    temperature: str = ""
    weight: str = ""
    spo2: str = ""
    prescription: str = ""
    advice: str = ""
    follow_up_date: str = ""


def _number(text: str, label: str, low: float, high: float, *, integer: bool) -> float:
    try:
        value = int(text) if integer else float(text)
    except ValueError:
        kind = "a whole number" if integer else "a number"
        raise ReportValidationError(f"{label} must be {kind}.") from None
    if not low <= value <= high:
        raise ReportValidationError(f"{label} must be between {low:g} and {high:g}.")
    return value


def _text(value: str, label: str, limit: int, *, required: bool = False) -> str | None:
    text = value.strip()
    if not text:
        if required:
            raise ReportValidationError(f"{label} is required.")
        return None
    if len(text) > limit:
        raise ReportValidationError(f"{label} can be at most {limit} characters.")
    return text


def normalise_draft(draft: ReportDraft, today: date | None = None) -> dict:
    """Validated report fields ready to store: blanks become None, numbers
    are checked against plausible clinical ranges, and the temperature
    keeps its unit (°C and °F are both in common use).
    """
    today = today or local_today()
    fields = {
        "chief_complaint": _text(
            draft.chief_complaint, "Chief complaint", MAX_SHORT_TEXT, required=True
        ),
        "diagnosis": _text(draft.diagnosis, "Diagnosis", MAX_SHORT_TEXT, required=True),
        "prescription": _text(draft.prescription, "Prescription", MAX_LONG_TEXT),
        "advice": _text(draft.advice, "Advice", MAX_LONG_TEXT),
        "blood_pressure": None,
        "pulse_rate": None,
        "temperature": None,
        "weight": None,
        "spo2": None,
        "follow_up_date": None,
    }

    if bp := draft.blood_pressure.strip():
        match = _BP_PATTERN.match(bp)
        if not match:
            raise ReportValidationError("Blood pressure should look like 120/80.")
        systolic, diastolic = int(match[1]), int(match[2])
        if not (50 <= systolic <= 260 and 30 <= diastolic <= 160 and systolic > diastolic):
            raise ReportValidationError("Check the blood pressure reading.")
        fields["blood_pressure"] = f"{systolic}/{diastolic}"

    if pulse := draft.pulse_rate.strip():
        fields["pulse_rate"] = str(int(_number(pulse, "Pulse", 20, 250, integer=True)))

    if temperature := draft.temperature.strip():
        value = _number(temperature, "Temperature", 30, 113, integer=False)
        if 30 <= value <= 45:
            fields["temperature"] = f"{value:g} °C"
        elif 86 <= value <= 113:
            fields["temperature"] = f"{value:g} °F"
        else:
            raise ReportValidationError("Temperature must be 30-45 °C or 86-113 °F.")

    if weight := draft.weight.strip():
        fields["weight"] = f"{_number(weight, 'Weight', 0.3, 400, integer=False):g}"

    if spo2 := draft.spo2.strip():
        fields["spo2"] = str(int(_number(spo2, "SpO₂", 50, 100, integer=True)))

    if follow_up := draft.follow_up_date.strip():
        try:
            if not _DATE_PATTERN.match(follow_up):
                raise ValueError
            follow_up_day = date.fromisoformat(follow_up)
        except ValueError:
            raise ReportValidationError("Follow-up date should be YYYY-MM-DD.") from None
        if follow_up_day < today:
            raise ReportValidationError("Follow-up date can't be in the past.")
        fields["follow_up_date"] = follow_up_day.isoformat()

    return fields


def create_report(
    conn: sqlite3.Connection,
    *,
    author: AuthenticatedUser,
    patient_id: str,
    draft: ReportDraft,
    token_id: str | None = None,
) -> dict:
    """Validate and save a report. Only doctors can author reports
    (PermissionError otherwise). Returns the saved report.
    """
    if author.role != Role.DOCTOR or author.doctor_id is None:
        raise PermissionError("Only doctors can write medical reports.")
    if not PatientsRepository(conn).exists(patient_id):
        raise ReportValidationError("That patient no longer exists.")
    if token_id is not None:
        token = QueueTokensRepository(conn).get(token_id)
        if token is None or token["patient_id"] != patient_id:
            raise ReportValidationError("That queue visit doesn't belong to this patient.")

    today = local_today()
    fields = normalise_draft(draft, today)
    repo = MedicalReportsRepository(conn)
    report_id = str(uuid4())

    conn.execute("BEGIN")
    try:
        repo.insert(
            {
                **fields,
                "report_id": report_id,
                "report_number": next_report_number(conn),
                "patient_id": patient_id,
                "doctor_id": author.doctor_id,
                "doctor_name": author.display_name,
                "dept_id": author.dept_id,
                "token_id": token_id,
                "visit_date": today.isoformat(),
            }
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return repo.get(report_id)


def list_reports(conn: sqlite3.Connection, patient_id: str) -> list[dict]:
    """A patient's reports, newest first."""
    return MedicalReportsRepository(conn).list_for_patient(patient_id)


def get_report(conn: sqlite3.Connection, report_id: str) -> dict | None:
    return MedicalReportsRepository(conn).get(report_id)


def report_count_for_token(conn: sqlite3.Connection, token_id: str) -> int:
    return MedicalReportsRepository(conn).count_for_token(token_id)
