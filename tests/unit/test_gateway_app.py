"""Import-level smoke tests only -- do not call the endpoints, since /health
and /sync/push both require a live Postgres connection. The real end-to-end
checks are in tests/integration/ against the docker-compose stack.

Paths are read from the OpenAPI schema rather than app.routes directly:
included routers (app.include_router) are represented as an internal
_IncludedRouter placeholder in app.routes on this FastAPI version, not
flattened route objects, so app.openapi()["paths"] is the stable way to ask
"what's actually registered" regardless of that internal representation.
"""

from gateway.main import app


def test_gateway_app_has_health_and_sync_routes():
    paths = set(app.openapi()["paths"].keys())
    assert "/health" in paths
    assert "/sync/push" in paths
