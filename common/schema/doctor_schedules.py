"""DDL for doctor_schedules: each doctor's weekly OPD hours (one slot per
doctor for the MVP -- e.g. Mon-Fri 09:00-13:00). Doctors set their own;
reception sees them on the Doctors page.

opd_days is a comma-separated list in week order ("Mon,Tue,Wed");
start_time/end_time are 24-hour "HH:MM", so plain text comparison orders
them correctly and the CHECK can enforce start before end.
"""

DDL = """
CREATE TABLE IF NOT EXISTS doctor_schedules (
    doctor_id   TEXT PRIMARY KEY REFERENCES doctors(doctor_id),
    opd_days    TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    CHECK (start_time < end_time)
);
"""
