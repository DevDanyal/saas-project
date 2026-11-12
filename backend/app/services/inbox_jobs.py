"""Background inbox jobs: sync, auto-process, and nightly digest prep."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import pipeline
from app.core.config import settings
from app.db import crud, models
from app.db.session import async_session
from app.services import billing, digest_service, gmail_sync

logger = logging.getLogger(__name__)


async def sync_and_process_user(
    db: AsyncSession,
    user_id,
    max_results: int | None = None,
    process_limit: int | None = None,
    llm=None,
) -> dict:
    max_results = max_results or settings.auto_process_max_results
    process_limit = process_limit or settings.auto_process_limit

    stats = {"user_id": str(user_id), "emails_processed": 0, "process_errors": 0}
    try:
        stats["sync"] = await gmail_sync.sync_user_inbox(
            db, user_id, max_results=max_results
        )
    except Exception as exc:
        await db.rollback()
        stats["sync_error"] = str(exc)
        return stats
    await db.commit()

    can_process, usage = await billing.check_email_limit(db, user_id)
    stats["limits"] = usage
    if not can_process:
        stats["limit_reached"] = True
        return stats

    email_ids = await crud.list_unprocessed_email_ids(db, user_id, limit=process_limit)
    for email_id in email_ids:
        try:
            await pipeline.process_email(db, email_id, llm=llm)
            await db.commit()
            stats["emails_processed"] += 1
        except Exception as exc:
            await db.rollback()
            stats["process_errors"] += 1
            logger.warning("Processing email %s failed: %s", email_id, exc)

    return stats


async def sync_and_process_all(
    session_factory: async_sessionmaker = async_session,
    max_results: int | None = None,
    process_limit: int | None = None,
    llm=None,
) -> dict:
    async with session_factory() as db:
        user_ids = await crud.list_active_gmail_user_ids(db)

    results = {}
    for user_id in user_ids:
        async with session_factory() as db:
            try:
                results[str(user_id)] = await sync_and_process_user(
                    db,
                    user_id,
                    max_results=max_results,
                    process_limit=process_limit,
                    llm=llm,
                )
            except Exception as exc:
                logger.exception("Inbox sync failed for %s", user_id)
                results[str(user_id)] = {"error": str(exc)}
    return results


async def generate_digests_all(
    session_factory: async_sessionmaker = async_session,
    llm=None,
    hours: int = 24,
) -> dict:
    async with session_factory() as db:
        user_ids = await crud.list_active_gmail_user_ids(db)

    results = {}
    for user_id in user_ids:
        async with session_factory() as db:
            try:
                payload = await digest_service.get_or_build_digest(
                    db, user_id, hours=hours, llm=llm
                )
                await db.commit()
                results[str(user_id)] = {
                    "brief": payload.get("brief", ""),
                    "threads_in_window": payload.get("threads_in_window", 0),
                }
                day_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                if not await crud.digest_notification_exists(db, user_id, day_start):
                    await crud.add_notification(
                        db,
                        user_id,
                        models.NotificationType.digest,
                        title="Morning digest ready",
                        body=f"Your brief: {payload.get('brief', '')[:60]}... ({payload.get('threads_in_window', 0)} threads, {payload.get('actions_in_window', 0)} actions)",
                    )
                await db.commit()
            except Exception as exc:
                await db.rollback()
                logger.exception("Digest generation failed for %s", user_id)
                results[str(user_id)] = {"error": str(exc)}
    return results


def digest_due(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now.hour >= settings.digest_hour_utc


def next_digest_window(now: datetime | None = None) -> datetime:
    """Start of the next digest window (used for logging)."""
    now = now or datetime.now(timezone.utc)
    candidate = now.replace(hour=settings.digest_hour_utc, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate
