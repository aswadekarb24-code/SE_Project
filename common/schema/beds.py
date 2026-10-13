"""DDL for beds: general bed matrix (no ward-level mapping per the MVP
scope), 1-click status toggle between AVAILABLE/OCCUPIED/MAINTENANCE.
"""

DDL = """
CREATE TABLE IF NOT EXISTS beds (
    bed_id      TEXT PRIMARY KEY,
    label       TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'AVAILABLE'
                CHECK (status IN ('AVAILABLE', 'OCCUPIED', 'MAINTENANCE')),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""
