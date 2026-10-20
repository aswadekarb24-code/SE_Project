"""DDL for patients, per the design doc: UUID PK (client-generated to avoid
offline collisions), NOT NULL on name/dob, indexed for sub-10ms lookups.

patient_number is the human-readable ID printed on reports and used at the
desk (e.g. PT-K7Q2-00042); see desktop/services/numbering.py for why it
embeds a station code. It's added to pre-existing databases by
desktop/data/db.py's upgrade step, which is also why its unique index lives
in NUMBER_INDEX_DDL instead of here: on an old database the column doesn't
exist yet when this DDL runs.
"""

DDL = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id      TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL,
    dob             TEXT NOT NULL,
    gender          TEXT,
    contact_no      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    patient_number  TEXT
);

CREATE INDEX IF NOT EXISTS idx_patients_full_name
    ON patients (full_name);
"""

NUMBER_INDEX_DDL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_patient_number
    ON patients (patient_number);
"""
