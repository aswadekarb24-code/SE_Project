"""Local SQLite connection management: WAL mode + migration bootstrap.

WAL (Write-Ahead Logging) is enabled so a reader never blocks a writer and vice
versa -- required for the <10ms local write latency target (NFR-01) and for
resilience against the power-interruption scenario called out in the SQA plan.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from common.schema.patients import DDL as PATIENTS_DDL
from common.schema.queue_tokens import DDL as QUEUE_TOKENS_DDL
from common.schema.sync_audit_log import DDL as SYNC_AUDIT_LOG_DDL

# Appended to as each cycle introduces new tables (doctors/beds/pharmacy_stock
# in Cycle 3). Order matters: patients must exist before queue_tokens (FK).
MIGRATIONS: list[str] = [
    SYNC_AUDIT_LOG_DDL,
    PATIENTS_DDL,
    QUEUE_TOKENS_DDL,
]

DEFAULT_DB_PATH = Path.home() / ".hms" / "hms.db"


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (creating if needed) the local SQLite DB in WAL mode."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply all known DDL. Idempotent (CREATE TABLE/INDEX IF NOT EXISTS)."""
    for ddl in MIGRATIONS:
        conn.executescript(ddl)
