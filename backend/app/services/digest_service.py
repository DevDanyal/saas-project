"""Build and cache the daily morning brief."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import digest
from app.db import crud, models


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def collect_digest_inputs(
    db: AsyncSession, user_id, hours: int = 24
) -> tuple[list[dict], list[dict]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    threads_res = await db.execute(
        select(models.Thread)
        .where(
            models.Thread.user_id == user_id,
            models.Thread.last_activity_at >= cutoff,
        )
        .order_by(models.Thread.last_activity_at.desc())
    )
    threads = [
        {
            "subject": t.subject,
            "category": t.category.value if t.category else None,
            "priority_score": t.priority_score,
            "flags": t.flags or [],
            "summary": t.summary,
            "last_activity_at": _iso(t.last_activity_at),
        }
        for t in threads_res.scalars().all()
    ]

    now = datetime.now(timezone.utc)
    actions_res = await db.execute(
        select(models.ActionItem)
        .join(models.Email)
        .join(models.Thread)
        .where(
            models.Thread.user_id == user_id,
            models.ActionItem.status == models.ActionStatus.open,
            models.ActionItem.due <= now + timedelta(days=7),
        )
        .order_by(models.ActionItem.due.asc().nulls_last())
    )
    actions = [
        {
            "type": a.type.value,
            "description": a.description,
            "due": _iso(a.due),
            "contact": a.contact,
        }
        for a in actions_res.scalars().all()
    ]
    return threads, actions


def _fallback_payload(threads: list[dict], actions: list[dict]) -> dict:
    """Deterministic brief used when the LLM is unavailable."""
    hot = [
        t.get("subject", "")
        for t in threads
        if (t.get("priority_score") or 0) >= 80 or "hot_lead" in (t.get("flags") or [])
    ]
    closings = [
        t.get("subject", "")
        for t in threads
        if "closing_deadline" in (t.get("flags") or [])
    ]
    follow_ups = [
        a.get("description", "") for a in actions if a.get("type") == "follow_up"
    ]
    other = [
        t.get("subject", "")
        for t in threads
        if t.get("subject", "") not in hot and t.get("subject", "") not in closings
    ]
    brief = (
        f"{len(hot)} hot leads, {len(closings)} closings, and "
        f"{len(follow_ups)} follow-ups need attention today."
    )
    return {
        "brief": brief,
        "sections": {
            "hot_leads": hot[:8],
            "closings": closings[:8],
            "follow_ups": follow_ups[:8],
            "other": other[:8],
        },
    }


def build_digest_payload(
    threads: list[dict], actions: list[dict], hours: int = 24, llm=None
) -> dict:
    try:
        brief = digest.build_digest(threads, actions, llm=llm)
        if not isinstance(brief, dict):
            raise ValueError("digest agent returned a non-object")
    except Exception:
        brief = _fallback_payload(threads, actions)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "threads_in_window": len(threads),
        "actions_in_window": len(actions),
        "brief": brief.get("brief", ""),
        "sections": brief.get("sections", {}),
    }


async def get_or_build_digest(
    db: AsyncSession,
    user_id,
    hours: int = 24,
    refresh: bool = False,
    llm=None,
) -> dict:
    """Return today's cached brief, building it when missing or forced.

    Caching keeps the dashboard from re-running an LLM call on every page view
    and lets the nightly job prepare the brief before the agent wakes up.
    """
    today = datetime.now(timezone.utc).date()
    if not refresh:
        cached = await crud.get_daily_digest(db, user_id, today)
        if cached is not None and (cached.payload or {}).get("window_hours") == hours:
            return cached.payload

    threads, actions = await collect_digest_inputs(db, user_id, hours=hours)
    payload = build_digest_payload(threads, actions, hours=hours, llm=llm)
    await crud.upsert_daily_digest(db, user_id, today, payload)
    return payload
