"""Generic sync_records table: (entity_name, record_id) -> latest known
payload + timestamp.

A single generic table -- rather than mirroring every hospital business
table's schema again in Postgres -- keeps the gateway simple and matches its
actual job for this MVP: hold the latest authoritative version of each
record for Last-Write-Wins conflict resolution and off-site backup, not run
hospital-side relational queries. Swapping this for Supabase later only
needs the same table (or an equivalent JSONB column) to exist there.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SyncRecordModel(Base):
    __tablename__ = "sync_records"

    entity_name = Column(String, primary_key=True)
    record_id = Column(String, primary_key=True)
    payload = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
