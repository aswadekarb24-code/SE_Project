"""Cloud sync gateway: /health (proves the Postgres connection works) and
/sync/push (Last-Write-Wins batch upsert, see routers/sync.py). A separate
patients/queue_tokens read API was considered but isn't needed for this
MVP's job -- off-site backup + conflict resolution, not hospital-side
queries against the cloud copy.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware

from gateway.config import REQUIRE_TLS
from gateway.db import engine
from gateway.models import Base
from gateway.routers.sync import router as sync_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="HMS Cloud Sync Gateway", lifespan=lifespan)
app.include_router(sync_router)

if REQUIRE_TLS:
    # NFR-02: refuse plain HTTP when TLS is expected to be in place (a
    # reverse proxy or uvicorn --ssl-certfile/--ssl-keyfile terminates it;
    # see gateway/config.py). Off by default so local docker-compose dev
    # -- which has no cert -- keeps working over plain HTTP.
    app.add_middleware(HTTPSRedirectMiddleware)


@app.get("/health")
def health() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
