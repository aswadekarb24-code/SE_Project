"""Staff accounts. Deliberately not logged to sync_audit_log: credential
hashes stay on this station (see common/schema/users.py).
"""

from __future__ import annotations

import sqlite3

from common.clock import now_iso

_COLUMNS = "user_id, username, full_name, role, doctor_id, password_hash, created_at, last_login_at"


def _to_dict(row: tuple) -> dict:
    return {
        "user_id": row[0],
        "username": row[1],
        "full_name": row[2],
        "role": row[3],
        "doctor_id": row[4],
        "password_hash": row[5],
        "created_at": row[6],
        "last_login_at": row[7],
    }


class UsersRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, user_id: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return None if row is None else _to_dict(row)

    def get_by_username(self, username: str) -> dict | None:
        # username is COLLATE NOCASE, so this lookup is case-insensitive.
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM users WHERE username = ?", (username,)
        ).fetchone()
        return None if row is None else _to_dict(row)

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def insert(
        self,
        *,
        user_id: str,
        username: str,
        full_name: str,
        role: str,
        password_hash: str,
        doctor_id: str | None = None,
    ) -> None:
        timestamp = now_iso()
        self._conn.execute(
            """INSERT INTO users
               (user_id, username, full_name, role, doctor_id, password_hash,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, full_name, role, doctor_id, password_hash, timestamp, timestamp),
        )

    def record_login(self, user_id: str) -> None:
        self._conn.execute(
            "UPDATE users SET last_login_at = ? WHERE user_id = ?", (now_iso(), user_id)
        )
