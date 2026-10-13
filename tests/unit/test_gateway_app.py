"""Import-level smoke test only -- does not call /health, since that requires a
live Postgres connection. The real end-to-end check is
tests/integration/test_gateway_health.py against the docker-compose stack.
"""

from gateway.main import app


def test_gateway_app_has_health_route():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
