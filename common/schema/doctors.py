"""DDL for doctors: availability lookup + self-service status toggle."""

DDL = """
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id   TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    dept_id     INTEGER NOT NULL REFERENCES departments(dept_id),
    status      TEXT NOT NULL DEFAULT 'AVAILABLE'
                CHECK (status IN ('AVAILABLE', 'BUSY', 'OFF_DUTY')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_doctors_dept
    ON doctors (dept_id);
"""
