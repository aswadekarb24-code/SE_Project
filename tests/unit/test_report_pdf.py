import pytest

from common.dto import PatientIntake
from desktop.export.report_pdf import export_report_pdf, report_html, suggested_filename
from desktop.services.patient_service import get_patient
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import ReportDraft, create_report


@pytest.fixture
def saved(db_conn, doctor):
    visit = issue_queue_token(
        db_conn, PatientIntake(full_name="Jane <b>Doe</b>", dob="1990-04-23", gender="Female"), 1
    )
    report = create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(
            chief_complaint="Headache & <script>alert(1)</script>",
            diagnosis="Migraine",
            temperature="98.6",
            prescription="Line one\nLine two",
        ),
    )
    return report, get_patient(db_conn, visit.patient_id)


def test_export_writes_a_pdf(qapp, tmp_path, saved):
    report, patient = saved
    path = export_report_pdf(report, patient, tmp_path / "report.pdf", "General OPD")

    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 2_000
    assert not list(tmp_path.glob("*.part"))  # temporary file cleaned up


def test_export_replaces_an_existing_file(qapp, tmp_path, saved):
    report, patient = saved
    target = tmp_path / "report.pdf"
    target.write_bytes(b"old")

    export_report_pdf(report, patient, target)
    assert target.read_bytes().startswith(b"%PDF")


def test_export_to_missing_folder_raises(qapp, tmp_path, saved):
    report, patient = saved
    with pytest.raises(OSError, match="Folder not found"):
        export_report_pdf(report, patient, tmp_path / "nope" / "report.pdf")


def test_user_text_is_escaped_in_the_document(saved):
    report, patient = saved
    html = report_html(report, patient, "General OPD")

    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>Doe</b>" not in html and "Jane &lt;b&gt;Doe&lt;/b&gt;" in html
    assert "Line one<br>Line two" in html
    assert report["report_number"] in html
    assert "98.6 °F" in html


def test_suggested_filename_drops_characters_windows_forbids(saved):
    report, patient = saved
    name = suggested_filename(report, {**patient, "full_name": 'A/B:C*D?"E"'})
    assert name == f"{report['report_number']} ABCDE.pdf"
