import pytest

from common.dto import PatientIntake
from desktop.services.patient_service import get_patient
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import ReportDraft, create_report, list_reports
from desktop.ui import report_dialogs
from desktop.ui.report_dialogs import ReportEditorDialog, ReportViewerDialog


@pytest.fixture
def visit(db_conn):
    return issue_queue_token(db_conn, PatientIntake(full_name="Jane Doe", dob="1990-04-23"), 1)


def test_editor_saves_a_report_for_the_visit(qapp, db_conn, doctor, visit):
    dialog = ReportEditorDialog(
        db_conn, doctor, get_patient(db_conn, visit.patient_id), token_id=visit.token_id
    )
    dialog.complaint_input.setPlainText("Fever")
    dialog.diagnosis_input.setText("Viral fever")
    dialog.temperature_input.setText("38.2")

    dialog.save()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.saved_report["temperature"] == "38.2 °C"
    assert dialog.saved_report["token_id"] == visit.token_id
    assert len(list_reports(db_conn, visit.patient_id)) == 1


def test_editor_shows_validation_errors_and_saves_nothing(qapp, db_conn, doctor, visit):
    dialog = ReportEditorDialog(db_conn, doctor, get_patient(db_conn, visit.patient_id))
    dialog.complaint_input.setPlainText("Fever")
    dialog.pulse_input.setText("fast")

    dialog.save()

    assert dialog.saved_report is None
    assert not dialog.error_label.isHidden()
    assert list_reports(db_conn, visit.patient_id) == []


def test_viewer_exports_pdf_to_the_chosen_file(qapp, db_conn, doctor, visit, tmp_path, monkeypatch):
    report = create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(chief_complaint="Fever", diagnosis="Viral fever"),
    )
    target = tmp_path / "jane"  # no extension typed: .pdf is added
    monkeypatch.setattr(
        report_dialogs.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "PDF documents (*.pdf)"),
    )
    viewer = ReportViewerDialog(db_conn, report, get_patient(db_conn, visit.patient_id))
    assert report["report_number"] in viewer.preview.toPlainText()

    viewer.export()

    assert viewer.exported_path == tmp_path / "jane.pdf"
    assert viewer.exported_path.read_bytes().startswith(b"%PDF")
    assert not viewer.status_label.isHidden()


def test_cancelled_export_writes_nothing(qapp, db_conn, doctor, visit, tmp_path, monkeypatch):
    report = create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(chief_complaint="Fever", diagnosis="Viral fever"),
    )
    monkeypatch.setattr(
        report_dialogs.QFileDialog, "getSaveFileName", lambda *args, **kwargs: ("", "")
    )
    viewer = ReportViewerDialog(db_conn, report, get_patient(db_conn, visit.patient_id))

    viewer.export()

    assert viewer.exported_path is None
    assert list(tmp_path.glob("*.pdf")) == []


def test_failed_export_warns_instead_of_crashing(
    qapp, db_conn, doctor, visit, tmp_path, monkeypatch
):
    report = create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(chief_complaint="Fever", diagnosis="Viral fever"),
    )
    monkeypatch.setattr(
        report_dialogs.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "missing" / "x.pdf"), ""),
    )
    warnings = []
    monkeypatch.setattr(
        report_dialogs.QMessageBox, "warning", lambda *args: warnings.append(args[1])
    )
    viewer = ReportViewerDialog(db_conn, report, get_patient(db_conn, visit.patient_id))

    viewer.export()

    assert warnings == ["Export failed"]
    assert viewer.exported_path is None
