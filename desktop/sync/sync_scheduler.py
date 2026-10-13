"""Thin QTimer wrapper driving SyncWorker.run_once() periodically, so the
desktop UI never has to poll for sync state itself (FR-03: sync must not
block UI interactions).

Implementation note: run_once() is async, but the app's event loop here is
the plain (non-asyncio) Qt loop. For the MVP, each tick runs run_once() to
completion via asyncio.run() -- a handful of small HTTP calls on a timer,
not per-keystroke work, so a brief synchronous call per tick is an
acceptable simplification. A future cycle could integrate qasync for a
fully non-blocking event loop if sync volume grows.
"""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import QTimer

from desktop.sync.sync_worker import SyncWorker


class SyncScheduler:
    def __init__(self, worker: SyncWorker, interval_seconds: float = 30.0) -> None:
        self._worker = worker
        self._timer = QTimer()
        self._timer.setInterval(int(interval_seconds * 1000))
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        asyncio.run(self._worker.run_once())
