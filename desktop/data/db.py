"""Local SQLite connection management: SQLCipher encryption-at-rest (NFR-02),
WAL mode, and migration bootstrap.

WAL (Write-Ahead Logging) is enabled so a reader never blocks a writer and vice
versa -- required for the <10ms local write latency target (NFR-01) and for
resilience against the power-interruption scenario called out in the SQA plan.

Connections are opened via sqlcipher3 (a drop-in build of the sqlite3 C
extension linked against SQLCipher instead of plain SQLite) rather than the
stdlib sqlite3 module, so the database file is encrypted at rest. Its
Connection/Cursor objects implement the same DB-API 2.0 surface as
sqlite3.Connection, so `sqlite3.Connection` type hints elsewhere in the
codebase remain accurate for duck-typing purposes -- no other file needs to
change for this.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from common.schema.beds import DDL as BEDS_DDL
from common.schema.departments import DDL as DEPARTMENTS_DDL
from common.schema.doctors import DDL as DOCTORS_DDL
from common.schema.patients import DDL as PATIENTS_DDL
from common.schema.pharmacy_stock import DDL as PHARMACY_STOCK_DDL
from common.schema.queue_tokens import DDL as QUEUE_TOKENS_DDL
from common.schema.sync_audit_log import DDL as SYNC_AUDIT_LOG_DDL

# Order matters: departments before doctors/queue_tokens (FK), patients
# before queue_tokens (FK).
MIGRATIONS: list[str] = [
    SYNC_AUDIT_LOG_DDL,
    DEPARTMENTS_DDL,
    PATIENTS_DDL,
    QUEUE_TOKENS_DDL,
    DOCTORS_DDL,
    BEDS_DDL,
    PHARMACY_STOCK_DDL,
]

DEFAULT_DB_PATH = Path.home() / ".hms" / "hms.db"

# INSECURE on purpose: a fixed fallback so `connect()` works out of the box
# for dev/tests without any setup. A real deployment MUST set
# HMS_DB_ENCRYPTION_KEY to a unique, secret value -- anyone with this
# source file otherwise knows the "encryption" key.
_INSECURE_DEV_DEFAULT_KEY = "dev-only-insecure-key-set-HMS_DB_ENCRYPTION_KEY"  # noqa: S105


def connect(
    db_path: Path | str = DEFAULT_DB_PATH, encryption_key: str | None = None
) -> sqlite3.Connection:
    """Open (creating if needed) the local SQLite DB, encrypted at rest via
    SQLCipher, in WAL mode.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    key = encryption_key or os.environ.get("HMS_DB_ENCRYPTION_KEY") or _INSECURE_DEV_DEFAULT_KEY

    conn = sqlcipher.connect(str(path), isolation_level=None)
    # PRAGMA statements don't support `?` parameter binding, so the key is
    # embedded as a SQL string literal with standard single-quote doubling
    # (the correct SQL escape, not ad-hoc) rather than passed as a param.
    escaped_key = key.replace("'", "''")
    conn.execute(f"PRAGMA key = '{escaped_key}';")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply all known DDL. Idempotent (CREATE TABLE/INDEX IF NOT EXISTS)."""
    for ddl in MIGRATIONS:
        conn.executescript(ddl)
