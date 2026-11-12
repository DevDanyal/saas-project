"""In-process background scheduler.

Enabled with SCHEDULER_ENABLED=true. Runs periodic sync + auto-processing and
one digest build per day after DIGEST_HOUR_UTC. For multi-replica deployments,
disable this and run the same jobs from a single worker/cron instead.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.services import inbox_jobs

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _loop() -> None:
    last_sync: datetime | None = None
    last_digest_date = None
    logger.info("Background scheduler started")

    while True:
        now = datetime.now(timezone.utc)

        due_sync = (
            last_sync is None
            or (now - last_sync).total_seconds() >= settings.sync_interval_minutes * 60
        )
        if due_sync:
            try:
                await inbox_jobs.sync_and_process_all()
            except Exception:
                logger.exception("Scheduled inbox sync failed")
            last_sync = datetime.now(timezone.utc)

        if inbox_jobs.digest_due(now) and last_digest_date != now.date():
            try:
                await inbox_jobs.generate_digests_all()
                last_digest_date = now.date()
                logger.info("Daily digests generated for %s", now.date())
            except Exception:
                logger.exception("Scheduled digest generation failed")

        await asyncio.sleep(max(5, settings.scheduler_tick_seconds))


def start_scheduler() -> None:
    global _task
    if not settings.scheduler_enabled:
        logger.info("Background scheduler disabled")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="inbox-scheduler")


async def stop_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("Background scheduler stopped")
