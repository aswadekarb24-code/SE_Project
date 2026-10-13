"""DDL for patients, per the design doc: UUID PK (client-generated to avoid
offline collisions), NOT NULL on name/dob, indexed for sub-10ms lookups.
"""

DDL = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id  TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    dob         TEXT NOT NULL,
    gender      TEXT,
    contact_no  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patients_full_name
    ON patients (full_name);
"""
