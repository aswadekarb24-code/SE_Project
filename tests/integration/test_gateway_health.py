"""Requires `docker compose up -d` to be running against the local gateway +
Postgres stack. Skips (rather than fails) if the stack isn't reachable, so
`pytest tests/unit` (no docker) stays fast and self-contained; CI's
`integration` job always brings the stack up first.
"""

import httpx
import pytest

GATEWAY_URL = "http://localhost:8000"


def _gateway_reachable() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/health", timeout=1.0)
        return True
    except httpx.TransportError:
        return False


@pytest.mark.skipif(not _gateway_reachable(), reason="gateway stack is not running")
def test_health_endpoint_reports_ok():
    response = httpx.get(f"{GATEWAY_URL}/health", timeout=5.0)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
