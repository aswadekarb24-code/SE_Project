"""Per-station settings stored in app_meta (local only, never synced)."""

from __future__ import annotations

import sqlite3

AUTO_PRINT_SLIPS = "auto_print_slips"


def get_flag(conn: sqlite3.Connection, key: str, default: bool = False) -> bool:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return default if row is None else row[0] == "1"


def set_flag(conn: sqlite3.Connection, key: str, value: bool) -> None:
    conn.execute(
        """INSERT INTO app_meta (key, value) VALUES (?, ?)
           ON CONFLICT (key) DO UPDATE SET value = excluded.value""",
        (key, "1" if value else "0"),
    )
