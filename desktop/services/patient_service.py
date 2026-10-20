"""Patient intake validation, lookup and visit history.

Every patient gets a permanent, human-readable patient number on
registration (desktop/data/numbering.py). Returning patients are looked up
by that number, their name or their phone number and checked in against
the same record, so their visits and reports accumulate in one history.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import replace
from datetime import date

from common.clock import local_today
from common.dto import PatientIntake
from desktop.data.repositories.patients_repo import PatientsRepository
from desktop.data.repositories.queue_tokens_repo import QueueTokensRepository

GENDERS = ("Female", "Male", "Other")
MAX_NAME_LENGTH = 100
MAX_AGE_YEARS = 130

_DOB_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CONTACT_ALLOWED = re.compile(r"^\+?[\d\s()-]+$")


class PatientValidationError(ValueError):
    """Intake data that can't be saved; the message is shown to the user."""


def parse_dob(dob: str, today: date | None = None) -> date:
    """A date of birth as YYYY-MM-DD that is a real date, not in the future
    and not implausibly old. Raises PatientValidationError otherwise.
    """
    today = today or local_today()
    text = dob.strip()
    if not _DOB_PATTERN.match(text):
        raise PatientValidationError("Enter the date of birth as YYYY-MM-DD, e.g. 1990-04-23.")
    try:
        value = date.fromisoformat(text)
    except ValueError:
        raise PatientValidationError(f"{text} isn't a real date.") from None
    if value > today:
        raise PatientValidationError("Date of birth can't be in the future.")
    if age_on(value, today) > MAX_AGE_YEARS:
        raise PatientValidationError(
            f"Check the date of birth: that's over {MAX_AGE_YEARS} years ago."
        )
    return value


def validate_intake(intake: PatientIntake, today: date | None = None) -> PatientIntake:
    """A cleaned-up copy of `intake` (whitespace trimmed, blanks as None).
    Raises PatientValidationError with a user-facing message on bad input.
    """
    full_name = " ".join(intake.full_name.split())
    if not full_name:
        raise PatientValidationError("Full name is required.")
    if len(full_name) > MAX_NAME_LENGTH:
        raise PatientValidationError(f"Full name can be at most {MAX_NAME_LENGTH} characters.")
    if not any(ch.isalpha() for ch in full_name):
        raise PatientValidationError("Full name must contain letters.")

    dob = parse_dob(intake.dob, today).isoformat()

    gender = (intake.gender or "").strip() or None
    if gender is not None and gender not in GENDERS:
        raise PatientValidationError(f"Gender must be one of: {', '.join(GENDERS)}.")

    contact_no = " ".join((intake.contact_no or "").split()) or None
    if contact_no is not None:
        digits = sum(ch.isdigit() for ch in contact_no)
        if not _CONTACT_ALLOWED.match(contact_no) or not 7 <= digits <= 15:
            raise PatientValidationError(
                "Contact number should be 7-15 digits (spaces, dashes and a leading + are fine)."
            )

    return replace(intake, full_name=full_name, dob=dob, gender=gender, contact_no=contact_no)


def age_on(dob: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (dob.month, dob.day)
    return today.year - dob.year - (0 if had_birthday else 1)


def age_sex(patient: dict, today: date | None = None) -> str:
    """Short demographic label, e.g. "34 y · Female" (or "8 mo" for infants)."""
    today = today or local_today()
    dob = date.fromisoformat(patient["dob"])
    years = age_on(dob, today)
    if years >= 1:
        age = f"{years} y"
    else:
        months = (today.year - dob.year) * 12 + today.month - dob.month
        if today.day < dob.day:
            months -= 1
        age = f"{max(months, 0)} mo"
    return f"{age} · {patient['gender']}" if patient.get("gender") else age


def search_patients(conn: sqlite3.Connection, query: str = "", limit: int = 200) -> list[dict]:
    return PatientsRepository(conn).search(query, limit)


def get_patient(conn: sqlite3.Connection, patient_id: str) -> dict | None:
    return PatientsRepository(conn).get(patient_id)


def list_visits(conn: sqlite3.Connection, patient_id: str) -> list[dict]:
    return QueueTokensRepository(conn).list_for_patient(patient_id)
