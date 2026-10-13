from desktop.sync.sync_scheduler import SyncScheduler


class _FakeWorker:
    def __init__(self) -> None:
        self.run_once_calls = 0

    async def run_once(self):
        self.run_once_calls += 1
        return []


def test_scheduler_start_and_stop_do_not_raise(qapp):
    scheduler = SyncScheduler(_FakeWorker(), interval_seconds=0.05)
    scheduler.start()
    scheduler.stop()


def test_tick_invokes_worker_run_once(qapp):
    worker = _FakeWorker()
    scheduler = SyncScheduler(worker, interval_seconds=30)

    scheduler._tick()

    assert worker.run_once_calls == 1
