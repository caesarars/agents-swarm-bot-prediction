"""APScheduler wrapper that drives the prediction loop."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import prediction

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _job_predict_safely() -> None:
    try:
        await prediction.run_prediction_round()
    except Exception as e:
        log.exception("prediction round failed: %s", e)


async def _job_settle_safely() -> None:
    try:
        await prediction.settle_due_predictions()
    except Exception as e:
        log.exception("settle round failed: %s", e)


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # Predict every 15 minutes, second 30, so the 15m candle has just closed.
    _scheduler.add_job(
        _job_predict_safely,
        CronTrigger(minute="*/15", second="30"),
        id="predict_round",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    # Settle every minute is cheap and only acts when target_at has passed.
    _scheduler.add_job(
        _job_settle_safely,
        CronTrigger(second="40"),
        id="settle_round",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
    )

    _scheduler.start()
    log.info("scheduler started")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
        _scheduler = None
