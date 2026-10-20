"""Thin QTimer wrapper driving SyncWorker.run_once() periodically, so the
desktop UI never has to poll for sync state itself (FR-03: sync must not
block UI interactions).

Implementation note: run_once() is async, but the app's event loop here is
the plain (non-asyncio) Qt loop. For the MVP, each tick runs run_once() to
completion via asyncio.run() -- a handful of small HTTP calls on a timer,
not per-keystroke work, so a brief synchronous call per tick is an
acceptable simplification. A future cycle could integrate qasync for a
fully non-blocking event loop if sync volume grows.

Each pass's outcome (time, results, error) is kept for the sync status bar.
An unexpected exception in a pass is recorded rather than raised: an
exception escaping a Qt timer slot would abort the whole app, and a sync
hiccup must never take the reception desk down (NFR-03).
"""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from common.clock import now_iso
from common.dto import SyncResult
from desktop.sync.sync_worker import SyncWorker


class SyncScheduler(QObject):
    # Emitted after every pass, successful or not.
    ran = pyqtSignal()

    def __init__(self, worker: SyncWorker, interval_seconds: float = 30.0) -> None:
        super().__init__()
        self._worker = worker
        self._timer = QTimer(self)
        self._timer.setInterval(int(interval_seconds * 1000))
        self._timer.timeout.connect(self._tick)
        self.last_attempt_at: str | None = None
        self.last_results: list[SyncResult] = []
        self.last_error: str | None = None

    @property
    def state(self):
        return getattr(self._worker, "state", None)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def sync_now(self) -> None:
        """Run a pass immediately (the status bar's Retry button)."""
        self._tick()

    def _tick(self) -> None:
        self.last_attempt_at = now_iso()
        try:
            self.last_results = list(asyncio.run(self._worker.run_once()) or [])
            self.last_error = None
        except Exception as error:  # noqa: BLE001 -- see module docstring
            self.last_results = []
            self.last_error = f"{type(error).__name__}: {error}"
        self.ran.emit()
