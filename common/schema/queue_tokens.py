"""DDL for queue_tokens, per the design doc: UUID PK, FK to patients,
composite index on (dept_id, status) for live display queries, plus an
(dept_id, issued_date) index for the per-day/per-department token numbering
query in IssueQueueToken().
"""

DDL = """
CREATE TABLE IF NOT EXISTS queue_tokens (
    token_id     TEXT PRIMARY KEY,
    patient_id   TEXT NOT NULL REFERENCES patients(patient_id),
    dept_id      INTEGER NOT NULL REFERENCES departments(dept_id),
    token_num    INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'WAITING'
                 CHECK (status IN ('WAITING', 'CALLED', 'DONE')),
    issued_date  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_queue_tokens_dept_status
    ON queue_tokens (dept_id, status);

CREATE INDEX IF NOT EXISTS idx_queue_tokens_dept_date
    ON queue_tokens (dept_id, issued_date);
"""
