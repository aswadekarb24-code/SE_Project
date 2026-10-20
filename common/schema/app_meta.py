"""DDL for app_meta: small key/value store for per-database settings that
aren't business data -- this station's code and its human-readable number
counters (see desktop/services/numbering.py). Local only, never synced.
"""

DDL = """
CREATE TABLE IF NOT EXISTS app_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""
