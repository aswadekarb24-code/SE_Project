from datetime import date

import pytest

from desktop.data.db import connect, migrate
from desktop.data.repositories.doctors_repo import DoctorsRepository
from desktop.data.seed import DOCTOR_SCHEDULES, seed_default_data
from desktop.services.doctor_service import (
    ScheduleError,
    broadcast_all_doctors,
    format_days,
    format_schedule,
    get_schedules,
    in_opd_on,
    set_doctor_status,
    set_schedule,
)
from desktop.sync.entity_registry import ENTITY_ROW_FETCHERS


class RecordingBroadcaster:
    def __init__(self):
        self.doctor_packets = []

    def broadcast_token_update(self, **kwargs):
        return True

    def broadcast_doctor_status(self, **kwargs):
        self.doctor_packets.append(kwargs)
        return True


@pytest.fixture
def doctor_id(db_conn):
    DoctorsRepository(db_conn).insert(doctor_id="d1", full_name="Dr. Asha Rao", dept_id=1)
    return "d1"


def test_set_schedule_stores_days_in_week_order(db_conn, doctor_id):
    saved = set_schedule(db_conn, doctor_id, ["Fri", "Mon", "Wed"], "09:00", "13:00")
    assert saved["opd_days"] == "Mon,Wed,Fri"
    assert get_schedules(db_conn)[doctor_id]["start_time"] == "09:00"


def test_updating_a_schedule_logs_insert_then_update(db_conn, doctor_id):
    set_schedule(db_conn, doctor_id, ["Mon"], "09:00", "10:00")
    set_schedule(db_conn, doctor_id, ["Tue"], "11:00", "12:00")

    logged = db_conn.execute(
        "SELECT action_type FROM sync_audit_log WHERE entity_name = 'doctor_schedules' "
        "ORDER BY sync_id"
    ).fetchall()
    assert logged == [("INSERT",), ("UPDATE",)]
    assert ENTITY_ROW_FETCHERS["doctor_schedules"](db_conn, doctor_id)["opd_days"] == "Tue"


@pytest.mark.parametrize(
    ("days", "start", "end", "message"),
    [
        ([], "09:00", "13:00", "at least one"),
        (["Mon", "Funday"], "09:00", "13:00", "Unknown day"),
        (["Mon"], "9:00", "13:00", "HH:MM"),
        (["Mon"], "09:00", "24:00", "HH:MM"),
        (["Mon"], "13:00", "09:00", "end after"),
        (["Mon"], "09:00", "09:00", "end after"),
    ],
)
def test_invalid_schedules_are_rejected(db_conn, doctor_id, days, start, end, message):
    with pytest.raises(ScheduleError, match=message):
        set_schedule(db_conn, doctor_id, days, start, end)
    assert get_schedules(db_conn) == {}


def test_schedule_for_unknown_doctor_is_rejected(db_conn):
    with pytest.raises(ScheduleError, match="no longer exists"):
        set_schedule(db_conn, "nobody", ["Mon"], "09:00", "10:00")


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (["Mon", "Tue", "Wed", "Thu", "Fri"], "Mon–Fri"),
        (["Mon", "Wed", "Fri"], "Mon, Wed, Fri"),
        (["Mon", "Tue", "Thu", "Fri", "Sat"], "Mon, Tue, Thu–Sat"),
        (["Sun"], "Sun"),
    ],
)
def test_format_days(days, expected):
    assert format_days(days) == expected


def test_format_schedule_and_today_check():
    schedule = {"opd_days": "Mon,Tue,Wed,Thu,Fri", "start_time": "09:00", "end_time": "13:00"}
    assert format_schedule(schedule) == "Mon–Fri · 09:00–13:00"
    assert format_schedule(None) == "No OPD hours set"
    assert in_opd_on(schedule, date(2026, 10, 20))  # a Tuesday
    assert not in_opd_on(schedule, date(2026, 10, 25))  # a Sunday
    assert not in_opd_on(None, date(2026, 10, 20))


def test_seed_gives_seeded_doctors_default_hours(db_conn):
    seed_default_data(db_conn)
    schedules = get_schedules(db_conn)
    names = {d["doctor_id"]: d["full_name"] for d in DoctorsRepository(db_conn).list_all()}
    assert {names[doctor_id] for doctor_id in schedules} == set(DOCTOR_SCHEDULES)

    seed_default_data(db_conn)  # idempotent
    assert len(get_schedules(db_conn)) == len(DOCTOR_SCHEDULES)


def test_seed_adds_hours_to_databases_seeded_before_schedules(tmp_path):
    conn = connect(tmp_path / "old.db")
    try:
        migrate(conn)
        DoctorsRepository(conn).insert(doctor_id="x", full_name="Dr. Asha Rao", dept_id=1)
        seed_default_data(conn)  # doctors table not empty, schedules table empty
        assert get_schedules(conn)["x"]["opd_days"] == DOCTOR_SCHEDULES["Dr. Asha Rao"][0]
    finally:
        conn.close()


def test_status_change_is_broadcast_to_displays(db_conn, doctor_id):
    broadcaster = RecordingBroadcaster()
    set_doctor_status(db_conn, doctor_id, "BUSY", broadcaster=broadcaster)
    assert broadcaster.doctor_packets == [
        {"doctor_id": "d1", "name": "Dr. Asha Rao", "dept_id": 1, "status": "BUSY"}
    ]


def test_broadcast_all_doctors_resends_every_status(db_conn, doctor_id):
    DoctorsRepository(db_conn).insert(doctor_id="d2", full_name="Dr. Meera Nair", dept_id=2)
    broadcaster = RecordingBroadcaster()
    broadcast_all_doctors(db_conn, broadcaster)
    assert sorted(p["doctor_id"] for p in broadcaster.doctor_packets) == ["d1", "d2"]
