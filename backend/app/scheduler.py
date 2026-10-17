from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.db import Database
from app.services.collector_service import (
    collect_debt_to_gdp,
    collect_government_expenditure,
    collect_gst_collection,
    collect_inflation,
    collect_monthly_trade,
    collect_nse_ticker,
    collect_world_bank_gdp,
)


logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def start_collector_scheduler(database: Database) -> bool:
    global _scheduler

    settings = get_settings()
    if not settings.collector_enabled:
        return False
    if _scheduler is not None and _scheduler.running:
        return True

    scheduler = AsyncIOScheduler(timezone=timezone.utc)
    scheduler.add_job(
        run_nse_collection,
        trigger=IntervalTrigger(minutes=settings.collector_interval_minutes),
        args=[database],
        id="nse_ticker_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.collector_interval_minutes * 60,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_world_bank_gdp_collection,
        trigger=IntervalTrigger(hours=24),
        args=[database],
        id="world_bank_gdp_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=86_400,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_debt_to_gdp_collection,
        trigger=IntervalTrigger(hours=24),
        args=[database],
        id="debt_to_gdp_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=86_400,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_trade_collection,
        trigger=IntervalTrigger(hours=settings.trade_refresh_hours),
        args=[database],
        id="monthly_trade_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.trade_refresh_hours * 3_600,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_gst_collection,
        trigger=IntervalTrigger(hours=settings.gst_refresh_hours),
        args=[database],
        id="gst_collection_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.gst_refresh_hours * 3_600,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_inflation_collection,
        trigger=IntervalTrigger(hours=settings.inflation_refresh_hours),
        args=[database],
        id="inflation_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.inflation_refresh_hours * 3_600,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.add_job(
        run_government_expenditure_collection,
        trigger=IntervalTrigger(hours=settings.expenditure_refresh_hours),
        args=[database],
        id="government_expenditure_collector",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=settings.expenditure_refresh_hours * 3_600,
        next_run_time=(datetime.now(timezone.utc) if settings.collector_run_on_startup else None),
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Collector scheduler started with an NSE interval of %s minutes.",
        settings.collector_interval_minutes,
    )
    return True


def stop_collector_scheduler() -> None:
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Collector scheduler stopped.")
    _scheduler = None


def collector_scheduler_running() -> bool:
    return _scheduler is not None and _scheduler.running


async def run_nse_collection(database: Database) -> None:
    try:
        result = await collect_nse_ticker(database)
    except Exception:
        logger.exception("NSE scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info(
            "NSE scheduled collection stored %s observations.", result.records_stored
        )
    else:
        logger.warning("NSE scheduled collection failed: %s", result.error)


async def run_world_bank_gdp_collection(database: Database) -> None:
    try:
        result = await collect_world_bank_gdp(database)
    except Exception:
        logger.exception("World Bank GDP scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info(
            "World Bank GDP scheduled collection stored %s observations.", result.records_stored
        )
    else:
        logger.warning("World Bank GDP scheduled collection failed: %s", result.error)


async def run_debt_to_gdp_collection(database: Database) -> None:
    try:
        result = await collect_debt_to_gdp(database)
    except Exception:
        logger.exception("Debt-to-GDP scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info("Debt-to-GDP scheduled collection stored %s observations.", result.records_stored)
    else:
        logger.warning("Debt-to-GDP scheduled collection failed: %s", result.error)


async def run_trade_collection(database: Database) -> None:
    try:
        result = await collect_monthly_trade(database)
    except Exception:
        logger.exception("Monthly trade scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info("Monthly trade scheduled collection stored %s observations.", result.records_stored)
    else:
        logger.warning("Monthly trade scheduled collection failed: %s", result.error)


async def run_gst_collection(database: Database) -> None:
    try:
        result = await collect_gst_collection(database)
    except Exception:
        logger.exception("GST scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info("GST scheduled collection stored %s observations.", result.records_stored)
    else:
        logger.warning("GST scheduled collection failed: %s", result.error)


async def run_inflation_collection(database: Database) -> None:
    try:
        result = await collect_inflation(database)
    except Exception:
        logger.exception("Inflation scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info("Inflation scheduled collection stored %s observations.", result.records_stored)
    else:
        logger.warning("Inflation scheduled collection failed: %s", result.error)


async def run_government_expenditure_collection(database: Database) -> None:
    try:
        result = await collect_government_expenditure(database)
    except Exception:
        logger.exception("Government expenditure scheduled collection stopped unexpectedly.")
        return

    if result.succeeded:
        logger.info(
            "Government expenditure scheduled collection stored %s observations.",
            result.records_stored,
        )
    else:
        logger.warning("Government expenditure scheduled collection failed: %s", result.error)
