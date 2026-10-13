"""Cloud sync gateway. Cycle 0: only /health exists, proving the docker-compose
Postgres wiring works end to end. routers/patients.py, queue_tokens.py, and
sync.py (the Last-Write-Wins endpoint) land in Cycle 4.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from gateway.db import engine

app = FastAPI(title="HMS Cloud Sync Gateway")


@app.get("/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
