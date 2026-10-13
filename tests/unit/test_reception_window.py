from desktop.ui.reception_window import ReceptionWindow


def test_issue_token_button_creates_patient_and_updates_status_label(qapp, db_conn):
    window = ReceptionWindow(db_conn)
    window.full_name_input.setText("Jane Doe")
    window.dob_input.setText("1990-01-01")

    window._on_issue_token()

    assert window.status_label.text() == "Token #1 issued (WAITING)"
    assert window.full_name_input.text() == ""  # form cleared after success

    count = db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    assert count == 1


def test_issue_token_rejects_invalid_dob(qapp, db_conn, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "desktop.ui.reception_window.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )

    window = ReceptionWindow(db_conn)
    window.full_name_input.setText("Jane Doe")
    window.dob_input.setText("not-a-date")

    window._on_issue_token()

    assert len(warnings) == 1
    assert window.status_label.text() == ""
    count = db_conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    assert count == 0


def test_issue_token_rejects_empty_name(qapp, db_conn, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "desktop.ui.reception_window.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )

    window = ReceptionWindow(db_conn)
    window.dob_input.setText("1990-01-01")

    window._on_issue_token()

    assert len(warnings) == 1
