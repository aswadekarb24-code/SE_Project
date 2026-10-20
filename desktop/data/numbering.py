"""Human-readable record numbers that stay unique across offline stations.

Records are keyed by UUIDs, but staff need something they can read out and
type: PT-K7Q2-00042 for a patient, RPT-K7Q2-00007 for a report. Several
stations can register patients while offline, so a plain running number
would collide once their data syncs. Each database therefore gets a random
4-character station code on first use, and numbers count up per station:
unique across stations with no coordination needed.

Call these inside the caller's transaction. If it rolls back, the counter
increment rolls back with it, so numbers are never skipped or handed out
twice.
"""

from __future__ import annotations

import secrets
import sqlite3

# Crockford base32: no I, L, O or U, so codes can't be misread as 1/0 or spell words.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
STATION_CODE_LENGTH = 4

PATIENT_PREFIX = "PT"
REPORT_PREFIX = "RPT"


def station_code(conn: sqlite3.Connection) -> str:
    """This database's station code, created on first call."""
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'station_code'").fetchone()
    if row is not None:
        return row[0]
    code = "".join(secrets.choice(_ALPHABET) for _ in range(STATION_CODE_LENGTH))
    conn.execute("INSERT INTO app_meta (key, value) VALUES ('station_code', ?)", (code,))
    return code


def _next_sequence(conn: sqlite3.Connection, counter_key: str) -> int:
    row = conn.execute(
        """INSERT INTO app_meta (key, value) VALUES (?, '1')
           ON CONFLICT (key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
           RETURNING value""",
        (counter_key,),
    ).fetchone()
    return int(row[0])


def _next_unused(conn: sqlite3.Connection, prefix: str, counter_key: str, exists_sql: str) -> str:
    code = station_code(conn)
    while True:
        number = f"{prefix}-{code}-{_next_sequence(conn, counter_key):05d}"
        # Normally the first number is free; this only loops if the counter
        # was ever reset behind numbers already in use.
        if conn.execute(exists_sql, (number,)).fetchone() is None:
            return number


def next_patient_number(conn: sqlite3.Connection) -> str:
    return _next_unused(
        conn,
        PATIENT_PREFIX,
        "patient_seq",
        "SELECT 1 FROM patients WHERE patient_number = ?",
    )


def next_report_number(conn: sqlite3.Connection) -> str:
    return _next_unused(
        conn,
        REPORT_PREFIX,
        "report_seq",
        "SELECT 1 FROM medical_reports WHERE report_number = ?",
    )
