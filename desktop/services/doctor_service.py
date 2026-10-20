"""Doctor availability (status toggle) and weekly OPD schedules.

Status changes are also broadcast to the LAN displays, so the waiting room
shows which doctors are available.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date

from desktop.broadcast.broadcaster import Broadcaster
from desktop.data.repositories.doctor_schedules_repo import DoctorSchedulesRepository
from desktop.data.repositories.doctors_repo import DoctorsRepository

STATUSES = ["AVAILABLE", "BUSY", "OFF_DUTY"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleError(ValueError):
    """An OPD schedule that can't be saved; the message is user-facing."""


def list_doctors(conn: sqlite3.Connection) -> list[dict]:
    return DoctorsRepository(conn).list_all()


def set_doctor_status(
    conn: sqlite3.Connection,
    doctor_id: str,
    status: str,
    *,
    broadcaster: Broadcaster | None = None,
) -> dict:
    if status not in STATUSES:
        raise ValueError(f"invalid doctor status: {status}")

    repo = DoctorsRepository(conn)
    doctors = {doctor["doctor_id"]: doctor for doctor in repo.list_all()}
    doctor = doctors.get(doctor_id)
    if doctor is None:
        raise ValueError(f"doctor {doctor_id} does not exist")

    conn.execute("BEGIN")
    try:
        repo.update_status(doctor_id, status)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    updated = {**doctor, "status": status}
    if broadcaster is not None:
        broadcast_doctor(broadcaster, updated)
    return updated


def broadcast_doctor(broadcaster: Broadcaster, doctor: dict) -> bool:
    return broadcaster.broadcast_doctor_status(
        doctor_id=doctor["doctor_id"],
        name=doctor["full_name"],
        dept_id=doctor["dept_id"],
        status=doctor["status"],
    )


def broadcast_all_doctors(conn: sqlite3.Connection, broadcaster: Broadcaster) -> None:
    """Re-send every doctor's status, so a display that started late (or
    missed a UDP packet) catches up.
    """
    for doctor in list_doctors(conn):
        broadcast_doctor(broadcaster, doctor)


# Schedules ---------------------------------------------------------------


def get_schedules(conn: sqlite3.Connection) -> dict[str, dict]:
    """Every doctor's schedule, keyed by doctor_id (doctors without one are absent)."""
    return DoctorSchedulesRepository(conn).list_all()


def set_schedule(
    conn: sqlite3.Connection, doctor_id: str, days: list[str], start_time: str, end_time: str
) -> dict:
    """Validate and save a doctor's weekly OPD hours. Raises ScheduleError."""
    if DoctorsRepository(conn).get(doctor_id) is None:
        raise ScheduleError("That doctor no longer exists.")
    unknown = [day for day in days if day not in WEEKDAYS]
    if unknown:
        raise ScheduleError(f"Unknown day: {', '.join(unknown)}.")
    if not days:
        raise ScheduleError("Pick at least one OPD day.")
    for value in (start_time, end_time):
        if not _TIME.match(value):
            raise ScheduleError("Times should be 24-hour HH:MM, e.g. 09:30.")
    if start_time >= end_time:
        raise ScheduleError("OPD hours must end after they start.")

    ordered = [day for day in WEEKDAYS if day in days]
    repo = DoctorSchedulesRepository(conn)
    conn.execute("BEGIN")
    try:
        repo.upsert(
            doctor_id=doctor_id,
            opd_days=",".join(ordered),
            start_time=start_time,
            end_time=end_time,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return repo.get(doctor_id)


def schedule_days(schedule: dict) -> list[str]:
    return [day for day in schedule["opd_days"].split(",") if day]


def format_days(days: list[str]) -> str:
    """["Mon","Tue","Wed","Fri"] -> "Mon–Wed, Fri" (consecutive days as ranges)."""
    indexes = sorted(WEEKDAYS.index(day) for day in days)
    runs: list[list[int]] = []
    for index in indexes:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    parts = []
    for run in runs:
        if len(run) >= 3:
            parts.append(f"{WEEKDAYS[run[0]]}–{WEEKDAYS[run[-1]]}")
        else:
            parts.extend(WEEKDAYS[i] for i in run)
    return ", ".join(parts)


def format_schedule(schedule: dict | None) -> str:
    """e.g. "Mon–Fri · 09:00–13:00", or a prompt when no hours are set."""
    if schedule is None:
        return "No OPD hours set"
    days = format_days(schedule_days(schedule))
    return f"{days} · {schedule['start_time']}–{schedule['end_time']}"


def in_opd_on(schedule: dict | None, day: date) -> bool:
    """Whether the schedule includes `day`'s weekday."""
    return schedule is not None and WEEKDAYS[day.weekday()] in schedule_days(schedule)
