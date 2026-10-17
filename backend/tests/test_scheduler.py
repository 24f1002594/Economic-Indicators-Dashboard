import asyncio

from app.config import get_settings
from app.scheduler import (
    collector_scheduler_running,
    start_collector_scheduler,
    stop_collector_scheduler,
)


def test_scheduler_stays_off_when_collector_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTOR_ENABLED", "false")
    get_settings.cache_clear()

    async def run() -> None:
        started = await start_collector_scheduler(object())
        assert not started
        assert not collector_scheduler_running()

    try:
        asyncio.run(run())
    finally:
        stop_collector_scheduler()
        get_settings.cache_clear()


def test_scheduler_starts_one_nse_job_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTOR_ENABLED", "true")
    monkeypatch.setenv("COLLECTOR_RUN_ON_STARTUP", "false")
    monkeypatch.setenv("COLLECTOR_INTERVAL_MINUTES", "5")
    get_settings.cache_clear()

    async def run() -> None:
        started = await start_collector_scheduler(object())
        assert started
        assert collector_scheduler_running()
        stop_collector_scheduler()
        assert not collector_scheduler_running()

    try:
        asyncio.run(run())
    finally:
        stop_collector_scheduler()
        get_settings.cache_clear()
