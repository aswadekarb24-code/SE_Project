"""1-click bed status cycling: AVAILABLE -> OCCUPIED -> MAINTENANCE -> AVAILABLE."""

from __future__ import annotations

import sqlite3

from desktop.data.repositories.beds_repo import BedsRepository

_CYCLE = {
    "AVAILABLE": "OCCUPIED",
    "OCCUPIED": "MAINTENANCE",
    "MAINTENANCE": "AVAILABLE",
}


def list_beds(conn: sqlite3.Connection) -> list[dict]:
    return BedsRepository(conn).list_all()


def toggle_bed(conn: sqlite3.Connection, bed_id: str) -> dict:
    repo = BedsRepository(conn)
    beds = {bed["bed_id"]: bed for bed in repo.list_all()}
    bed = beds.get(bed_id)
    if bed is None:
        raise ValueError(f"bed {bed_id} does not exist")

    next_status = _CYCLE[bed["status"]]
    conn.execute("BEGIN")
    try:
        repo.update_status(bed_id, next_status)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return {**bed, "status": next_status}
