import importlib
from datetime import date, datetime, timedelta, timezone

import pytest

from common.clock import local_today
from common.dto import PatientIntake
from desktop.services.day_service import active_days, day_bounds, day_overview
from desktop.services.queue_service import issue_queue_token
from desktop.services.report_service import ReportDraft, create_report
from desktop.ui import app_shell
from desktop.ui.day_overview import DayOverviewDialog

DAY = date(2026, 10, 20)


def _issue(conn, name="Jane Doe"):
    return issue_queue_token(conn, PatientIntake(full_name=name, dob="1990-01-01"), 1)


def _move(conn, token, created_at: str):
    conn.execute(
        "UPDATE queue_tokens SET created_at = ? WHERE token_id = ?", (created_at, token.token_id)
    )
    conn.execute(
        "UPDATE patients SET created_at = ? WHERE patient_id = ?", (created_at, token.patient_id)
    )


def _shift(iso: str, **delta) -> str:
    moment = datetime.fromisoformat(iso) + timedelta(**delta)
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def test_day_bounds_cover_exactly_one_local_day():
    start, end = day_bounds(DAY)
    local_start = datetime.fromisoformat(start).astimezone()
    local_end = datetime.fromisoformat(end).astimezone()
    assert (local_start.date(), local_start.hour, local_start.minute) == (DAY, 0, 0)
    assert local_end.date() == DAY + timedelta(days=1)
    assert start.endswith("+00:00") and len(start) == len("2026-10-20T00:00:00.000000+00:00")


def test_overview_uses_local_midnight_boundaries(db_conn):
    start, end = day_bounds(DAY)
    first, last, before, after = (_issue(db_conn, n) for n in ("First", "Last", "Before", "After"))
    _move(db_conn, first, start)  # exactly local midnight: included
    _move(db_conn, last, _shift(end, microseconds=-1))  # last microsecond of the day
    _move(db_conn, before, _shift(start, microseconds=-1))  # previous day
    _move(db_conn, after, end)  # next day's midnight: excluded

    overview = day_overview(db_conn, DAY, include_reports=False)

    assert [v["full_name"] for v in overview["visits"]] == ["First", "Last"]
    assert [p["full_name"] for p in overview["registrations"]] == ["First", "Last"]
    assert overview["reports"] == []


def test_reports_only_for_doctors(db_conn, doctor):
    visit = _issue(db_conn)
    create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(chief_complaint="Cough", diagnosis="Cold"),
    )
    today = local_today()

    assert day_overview(db_conn, today, include_reports=False)["reports"] == []
    reports = day_overview(db_conn, today, include_reports=True)["reports"]
    assert [(r["diagnosis"], r["full_name"]) for r in reports] == [("Cold", "Jane Doe")]


def test_active_days_finds_busy_days(db_conn):
    start, _ = day_bounds(DAY)
    token = _issue(db_conn)
    _move(db_conn, token, _shift(start, hours=9))
    assert active_days(db_conn, date(2026, 10, 1), date(2026, 10, 31)) == {DAY}
    assert active_days(db_conn, date(2026, 11, 1), date(2026, 11, 30)) == set()


def test_dialog_lists_today_and_hides_reports_from_reception(qapp, db_conn, receptionist):
    _issue(db_conn)
    dialog = DayOverviewDialog(db_conn, receptionist)

    assert dialog.day == local_today()
    assert dialog.day_label.text().startswith("Today")
    assert dialog.visits_table.rowCount() == 1
    assert dialog.registrations_table.rowCount() == 1
    assert len(dialog.tabs.buttons) == 2  # no Reports tab for receptionists
    assert dialog.calendar.maximumDate().toPyDate() == local_today()  # no future days


def test_doctor_sees_reports_and_picking_another_day_reloads(qapp, db_conn, doctor):
    visit = _issue(db_conn)
    create_report(
        db_conn,
        author=doctor,
        patient_id=visit.patient_id,
        draft=ReportDraft(chief_complaint="Cough", diagnosis="Cold"),
    )
    dialog = DayOverviewDialog(db_conn, doctor)
    assert len(dialog.tabs.buttons) == 3
    assert dialog.reports_table.rowCount() == 1

    dialog.show_day(local_today() - timedelta(days=30))

    assert dialog.visits_table.rowCount() == 0
    assert dialog._pages[0].currentIndex() == 1  # empty state shown


def test_double_click_opens_the_patient(qapp, db_conn, receptionist):
    visit = _issue(db_conn)
    dialog = DayOverviewDialog(db_conn, receptionist)
    opened = []
    dialog.open_patient.connect(opened.append)

    dialog._open_patient_at(dialog.visits_table, 0)

    assert opened == [visit.patient_id]


def test_shell_date_chip_opens_calendar_and_navigates(qapp, db_conn, receptionist, monkeypatch):
    visit = _issue(db_conn)

    def fake_exec(dialog):
        dialog.open_patient.emit(visit.patient_id)
        return 1

    monkeypatch.setattr(app_shell.DayOverviewDialog, "exec", fake_exec)
    shell = app_shell.AppShell(db_conn, receptionist)

    shell.date_button.click()

    assert shell.current_key == "patients"
    assert shell.pages["patients"].detail_stack.currentIndex() == 1
    shell.sync_chip.stop()


@pytest.fixture
def fresh_config(monkeypatch):
    monkeypatch.delenv("HMS_SYNC_INTERVAL_SECONDS", raising=False)
    import desktop.config

    yield importlib.reload(desktop.config)
    importlib.reload(desktop.config)


def test_cloud_sync_runs_hourly_by_default(fresh_config):
    assert fresh_config.SYNC_INTERVAL_SECONDS == 3600
    assert fresh_config.STARTUP_SYNC_DELAY_SECONDS == 5


def test_sync_interval_can_still_be_overridden(monkeypatch):
    import desktop.config

    monkeypatch.setenv("HMS_SYNC_INTERVAL_SECONDS", "120")
    try:
        assert importlib.reload(desktop.config).SYNC_INTERVAL_SECONDS == 120
    finally:
        monkeypatch.delenv("HMS_SYNC_INTERVAL_SECONDS")
        importlib.reload(desktop.config)


def test_main_window_schedules_hourly_sync_and_a_startup_pass(qapp, tmp_path, fresh_config):
    from desktop import main

    importlib.reload(main)  # pick up the freshly loaded config
    window = main.MainWindow(db_path=tmp_path / "hms.db")
    try:
        assert window.sync_scheduler._timer.interval() == 3_600_000
        assert window.startup_sync.isSingleShot()
        assert window.startup_sync.interval() == 5_000
        assert window.startup_sync.isActive()
    finally:
        window.close()
    assert not window.startup_sync.isActive()


def test_dotenv_supplies_only_sync_settings(tmp_path, monkeypatch):
    from desktop import config

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "DATABASE_URL=postgresql://secret@host/db\n"
        'HMS_GATEWAY_URL="http://gateway:8000"\n'
        "HMS_DB_ENCRYPTION_KEY=not-for-the-desktop\n"
        "HMS_SYNC_INTERVAL_SECONDS=600\n",
        encoding="utf-8",
    )
    for key in ("HMS_GATEWAY_URL", "HMS_SYNC_INTERVAL_SECONDS", "HMS_DB_ENCRYPTION_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HMS_LOAD_DOTENV", "1")

    config.load_dotenv(tmp_path / "missing.env", env_file)

    import os

    assert os.environ["HMS_GATEWAY_URL"] == "http://gateway:8000"
    assert os.environ["HMS_SYNC_INTERVAL_SECONDS"] == "600"
    assert "DATABASE_URL" not in os.environ
    assert "HMS_DB_ENCRYPTION_KEY" not in os.environ
    for key in ("HMS_GATEWAY_URL", "HMS_SYNC_INTERVAL_SECONDS"):
        monkeypatch.delenv(key)


def test_dotenv_never_overrides_real_environment(tmp_path, monkeypatch):
    from desktop import config

    env_file = tmp_path / ".env"
    env_file.write_text("HMS_GATEWAY_URL=http://from-file\n", encoding="utf-8")
    monkeypatch.setenv("HMS_LOAD_DOTENV", "1")
    monkeypatch.setenv("HMS_GATEWAY_URL", "http://from-shell")

    config.load_dotenv(env_file)

    import os

    assert os.environ["HMS_GATEWAY_URL"] == "http://from-shell"
