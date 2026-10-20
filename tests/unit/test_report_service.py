from datetime import date

import pytest

from common.dto import PatientIntake
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import (
    ReportDraft,
    ReportValidationError,
    create_report,
    list_reports,
    normalise_draft,
    report_count_for_token,
)
from desktop.sync.entity_registry import ENTITY_ROW_FETCHERS

TODAY = date(2026, 10, 20)


@pytest.fixture
def visit(db_conn):
    return issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-04-23"), 1)


def _draft(**overrides):
    fields = {"chief_complaint": "Fever for 3 days", "diagnosis": "Viral fever"}
    fields.update(overrides)
    return ReportDraft(**fields)


def test_doctor_can_write_a_report(db_conn, doctor, visit):
    report = create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        token_id=visit.token_id,
        draft=_draft(blood_pressure="120 / 80", prescription="Paracetamol 500mg\nORS"),
    )

    assert report["report_number"].startswith("RPT-")
    assert report["doctor_name"] == "Dr. Asha Rao"
    assert report["dept_id"] == 1
    assert report["blood_pressure"] == "120/80"
    assert report["prescription"] == "Paracetamol 500mg\nORS"
    assert report["pulse_rate"] is None  # blank optional field
    assert report_count_for_token(db_conn, visit.token_id) == 1


def test_receptionist_cannot_write_reports(db_conn, receptionist, visit):
    with pytest.raises(PermissionError):
        create_report(db_conn, author=receptionist, patient_id=visit.patient_id, draft=_draft())
    assert list_reports(db_conn, visit.patient_id) == []


def test_unknown_patient_is_rejected(db_conn, doctor):
    with pytest.raises(ReportValidationError, match="no longer exists"):
        create_report(db_conn, author=doctor, patient_id="missing", draft=_draft())


def test_token_must_belong_to_the_patient(db_conn, doctor, visit):
    other = issue_queue_token(db_conn, PatientIntake(full_name="John Roe", dob="1980-01-01"), 1)
    with pytest.raises(ReportValidationError, match="doesn't belong"):
        create_report(
            db_conn,
            author=doctor,
            patient_id=visit.patient_id,
            token_id=other.token_id,
            draft=_draft(),
        )


def test_history_keeps_every_report_newest_first(db_conn, doctor, visit):
    first = create_report(db_conn, author=doctor, patient_id=visit.patient_id, draft=_draft())
    second = create_report(
        db_conn, author=doctor, patient_id=visit.patient_id, draft=_draft(diagnosis="Recovered")
    )

    reports = list_reports(db_conn, visit.patient_id)
    assert [r["report_id"] for r in reports] == [second["report_id"], first["report_id"]]
    assert first["report_number"] != second["report_number"]


def test_reports_are_queued_for_sync(db_conn, doctor, visit):
    report = create_report(db_conn, author=doctor, patient_id=visit.patient_id, draft=_draft())

    logged = db_conn.execute(
        "SELECT action_type FROM sync_audit_log WHERE entity_name = 'medical_reports' "
        "AND record_id = ?",
        (report["report_id"],),
    ).fetchall()
    assert logged == [("INSERT",)]
    assert ENTITY_ROW_FETCHERS["medical_reports"](db_conn, report["report_id"]) == report


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"chief_complaint": "  "}, "Chief complaint is required"),
        ({"diagnosis": ""}, "Diagnosis is required"),
        ({"blood_pressure": "120-80"}, "look like 120/80"),
        ({"blood_pressure": "80/120"}, "Check the blood pressure"),
        ({"pulse_rate": "fast"}, "whole number"),
        ({"pulse_rate": "400"}, "between 20 and 250"),
        ({"temperature": "60"}, "30-45 °C or 86-113 °F"),
        ({"weight": "-3"}, "between"),
        ({"spo2": "101"}, "between 50 and 100"),
        ({"follow_up_date": "2026-10-19"}, "past"),
        ({"follow_up_date": "next week"}, "YYYY-MM-DD"),
        ({"diagnosis": "x" * 501}, "at most 500"),
    ],
)
def test_invalid_drafts_are_rejected(overrides, message):
    with pytest.raises(ReportValidationError, match=message):
        normalise_draft(_draft(**overrides), TODAY)


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("37.5", "37.5 °C"), ("98.6", "98.6 °F"), ("39", "39 °C")],
)
def test_temperature_keeps_its_unit(typed, stored):
    assert normalise_draft(_draft(temperature=typed), TODAY)["temperature"] == stored


def test_follow_up_today_is_allowed():
    assert normalise_draft(_draft(follow_up_date="2026-10-20"), TODAY)["follow_up_date"] == (
        "2026-10-20"
    )
