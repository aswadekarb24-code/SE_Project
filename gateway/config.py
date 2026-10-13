"""Gateway deployment config (NFR-02: HTTPS/TLS 1.3 for cloud transport).

Local dev over docker-compose has no TLS cert, so this is opt-in: unset in
dev, required in any real deployment. A reverse proxy (or uvicorn's
--ssl-certfile/--ssl-keyfile) terminates TLS; HMS_REQUIRE_TLS just makes the
app itself refuse to serve plain HTTP when that's expected to be in place.
"""

from __future__ import annotations

import os

REQUIRE_TLS = os.environ.get("HMS_REQUIRE_TLS", "false").lower() == "true"
