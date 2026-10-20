from datetime import date

import pytest

from common.dto import PatientIntake
from desktop.services.patient_service import (
    PatientValidationError,
    age_sex,
    list_visits,
    search_patients,
    validate_intake,
)
from desktop.services.queue_service import issue_queue_token

TODAY = date(2026, 10, 20)


def _intake(**overrides):
    fields = {"full_name": "Jane Doe", "dob": "1990-04-23"}
    fields.update(overrides)
    return PatientIntake(**fields)


def test_valid_intake_is_cleaned_up():
    cleaned = validate_intake(
        _intake(full_name="  Jane   Doe ", gender="", contact_no=" +91 98765  43210 "), TODAY
    )
    assert cleaned.full_name == "Jane Doe"
    assert cleaned.gender is None
    assert cleaned.contact_no == "+91 98765 43210"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"full_name": "   "}, "Full name is required"),
        ({"full_name": "12345"}, "letters"),
        ({"full_name": "x" * 101}, "at most 100"),
        ({"dob": "23-04-1990"}, "YYYY-MM-DD"),
        ({"dob": "1990-02-30"}, "isn't a real date"),
        ({"dob": "2026-10-21"}, "future"),
        ({"dob": "1880-01-01"}, "over 130 years"),
        ({"gender": "Robot"}, "Gender"),
        ({"contact_no": "12345"}, "7-15 digits"),
        ({"contact_no": "call me maybe"}, "7-15 digits"),
    ],
)
def test_invalid_intake_is_rejected(overrides, message):
    with pytest.raises(PatientValidationError, match=message):
        validate_intake(_intake(**overrides), TODAY)


def test_born_today_is_valid():
    assert validate_intake(_intake(dob="2026-10-20"), TODAY).dob == "2026-10-20"


def test_issue_token_rejects_invalid_new_patient_without_writing(db_conn):
    with pytest.raises(PatientValidationError):
        issue_queue_token(db_conn, _intake(dob="1990-13-01"), 1)
    assert db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0
    assert db_conn.execute("SELECT COUNT(*) FROM queue_tokens").fetchone()[0] == 0


@pytest.mark.parametrize(
    ("dob", "gender", "expected"),
    [
        ("1990-10-20", "Female", "36 y · Female"),
        ("1990-10-21", "Male", "35 y · Male"),  # birthday is tomorrow
        ("2026-03-25", None, "6 mo"),
        ("2026-10-01", None, "0 mo"),
    ],
)
def test_age_sex_label(dob, gender, expected):
    assert age_sex({"dob": dob, "gender": gender}, TODAY) == expected


def test_search_matches_number_name_and_phone(db_conn):
    jane = issue_queue_token(db_conn, _intake(contact_no="98765 43210"), 1)
    issue_queue_token(db_conn, _intake(full_name="John Roe", dob="1985-01-01"), 1)

    assert [p["full_name"] for p in search_patients(db_conn, "jane")] == ["Jane Doe"]
    assert [p["full_name"] for p in search_patients(db_conn, jane.patient_number.lower())] == [
        "Jane Doe"
    ]
    assert [p["full_name"] for p in search_patients(db_conn, "43210")] == ["Jane Doe"]
    assert len(search_patients(db_conn, "")) == 2


def test_search_treats_like_wildcards_literally(db_conn):
    issue_queue_token(db_conn, _intake(), 1)
    assert search_patients(db_conn, "%") == []
    assert search_patients(db_conn, "_") == []


def test_visit_history_lists_every_token_newest_first(db_conn):
    first = issue_queue_token(db_conn, _intake(), 1)
    issue_queue_token(
        db_conn, PatientIntake("Jane Doe", "1990-04-23", patient_id=first.patient_id), 2
    )

    visits = list_visits(db_conn, first.patient_id)
    assert [v["dept_name"] for v in visits] == ["Pediatrics", "General OPD"]
