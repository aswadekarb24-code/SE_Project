"""DDL for sync_audit_log: the single source of truth for "what needs syncing".

Every business-table mutation made locally also inserts a row here. The sync
worker only ever reads PENDING rows from this table -- it never scans business
tables directly. action_type is constrained to INSERT/UPDATE/DELETE per the
design doc's CHECK constraint.
"""

DDL = """
CREATE TABLE IF NOT EXISTS sync_audit_log (
    sync_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('INSERT', 'UPDATE', 'DELETE')),
    sync_status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (sync_status IN ('PENDING', 'SYNCED', 'CONFLICT')),
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_audit_log_status
    ON sync_audit_log (sync_status);
"""
