"""DDL for medical_reports: one consultation report per row, written by a
doctor for a patient. Append-only by design -- the app never updates or
deletes a saved report, so a patient's medical history is preserved
exactly as signed. A correction is a new report.

doctor_name is stored alongside doctor_id so the report keeps the author's
name as it was when signed. token_id links the report to the queue visit
it was written during (NULL when written outside a queue visit).
"""

DDL = """
CREATE TABLE IF NOT EXISTS medical_reports (
    report_id        TEXT PRIMARY KEY,
    report_number    TEXT NOT NULL UNIQUE,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    doctor_id        TEXT REFERENCES doctors(doctor_id),
    doctor_name      TEXT NOT NULL,
    dept_id          INTEGER REFERENCES departments(dept_id),
    token_id         TEXT REFERENCES queue_tokens(token_id),
    visit_date       TEXT NOT NULL,
    chief_complaint  TEXT NOT NULL,
    blood_pressure   TEXT,
    pulse_rate       TEXT,
    temperature      TEXT,
    weight           TEXT,
    spo2             TEXT,
    diagnosis        TEXT NOT NULL,
    prescription     TEXT,
    advice           TEXT,
    follow_up_date   TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_medical_reports_patient
    ON medical_reports (patient_id, created_at);

CREATE INDEX IF NOT EXISTS idx_medical_reports_doctor
    ON medical_reports (doctor_id, created_at);
"""
