"""Gateway's connection to Postgres -- local docker-compose today, Supabase later.

DATABASE_URL is the whole DI boundary at the infrastructure level: pointing it
at docker-compose's local Postgres vs. a real Supabase project is an env-var
change only, never a code change.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://hms:hms@localhost:5433/hms",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
