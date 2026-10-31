import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agents import digest, pipeline
from app.core.config import settings
from app.core.security import ensure_self, require_user
from app.db import crud, models
from app.db.session import get_session
from app.services import billing, gmail_sync

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/emails", tags=["emails"])


class SendDraftRequest(BaseModel):
    text: str | None = None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _thread_summary(t: models.Thread, unread_count: int = 0) -> dict:
    return {
        "id": str(t.id),
        "subject": t.subject,
        "category": t.category.value if t.category else None,
        "priority_score": t.priority_score,
        "flags": t.flags or [],
        "pipeline_hints": t.pipeline_hints or [],
        "summary": t.summary,
        "last_activity_at": _iso(t.last_activity_at),
        "emails": unread_count,
    }


@router.post("/sync/{user_id}")
@limiter.limit("10/hour")
async def sync_inbox(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    try:
        stats = await gmail_sync.sync_user_inbox(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return stats


@router.post("/process/{email_id}")
@limiter.limit("60/minute")
async def process_email(
    request: Request,
    email_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    email = await db.get(models.Email, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    thread = await db.get(models.Thread, email.thread_id)
    if not thread or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Email not found")

    can_process, usage = await billing.check_email_limit(db, str(thread.user_id))
    if not can_process:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Monthly email processing limit reached",
                "usage": usage,
                "upgrade_url": f"{settings.frontend_url}/billing",
            },
        )

    try:
        result = await pipeline.process_email(db, email_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await db.commit()
    return result


@router.post("/process-all/{user_id}")
@limiter.limit("5/hour")
async def process_inbox(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Run the AI pipeline over every synced email that hasn't been processed."""
    ensure_self(user, user_id)
    can_process, usage = await billing.check_email_limit(db, str(user_id))
    if not can_process:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Monthly email processing limit reached",
                "usage": usage,
                "upgrade_url": f"{settings.frontend_url}/billing",
            },
        )

    result = await db.execute(
        select(models.Email)
        .join(models.Thread)
        .where(models.Thread.user_id == user_id, models.Email.ai_summary.is_(None))
    )
    emails = result.scalars().all()
    processed, errors = 0, 0
    for email in emails:
        can_process, _ = await billing.check_email_limit(db, str(user_id))
        if not can_process:
            break
        try:
            await pipeline.process_email(db, email.id)
            processed += 1
        except Exception:
            errors += 1
    await db.commit()
    return {"processed": processed, "errors": errors, "pending": len(emails)}


@router.post("/drafts/{draft_id}/send")
@limiter.limit("30/minute")
async def send_draft(
    request: Request,
    draft_id: uuid.UUID,
    body: SendDraftRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Send an AI draft reply through Gmail and mark it sent."""
    draft = await db.get(models.AiDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft_email = await db.get(models.Email, draft.email_id)
    draft_thread = (
        await db.get(models.Thread, draft_email.thread_id) if draft_email else None
    )
    if draft_thread is None or draft_thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    try:
        result = await gmail_sync.send_draft_reply(db, draft_id, text=body.text)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail send failed: {e}")
    await db.commit()
    return result


@router.get("/inbox/{user_id}")
@limiter.limit("60/minute")
async def inbox(
    request: Request,
    user_id: uuid.UUID,
    limit: int = 100,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    threads = await crud.list_threads_for_user(db, user_id, limit=limit)
    return {"threads": [_thread_summary(t) for t in threads]}


@router.get("/threads/{thread_id}")
@limiter.limit("60/minute")
async def thread_detail(
    request: Request,
    thread_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    thread = await crud.get_thread_detail(db, thread_id)
    if thread is None or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Thread not found")
    emails = await crud.list_emails_for_thread(db, thread_id)

    drafts_res = await db.execute(
        select(models.AiDraft).where(models.AiDraft.email_id.in_([e.id for e in emails]))
    )
    drafts = {d.email_id: d for d in drafts_res.scalars().all()}
    actions_res = await db.execute(
        select(models.ActionItem).where(models.ActionItem.email_id.in_([e.id for e in emails]))
    )
    actions = {a.id: a for a in actions_res.scalars().all()}

    return {
        **_thread_summary(thread, unread_count=len(emails)),
        "emails": [
            {
                "id": str(e.id),
                "from_addr": e.from_addr,
                "to_addr": e.to_addr,
                "subject": e.subject,
                "received_at": _iso(e.received_at),
                "body": e.body,
                "ai_summary": e.ai_summary,
                "sentiment": e.sentiment,
                "has_attachment": e.has_attachment,
                "draft": (
                    {
                        "id": str(drafts[e.id].id),
                        "text": drafts[e.id].text,
                        "tone": drafts[e.id].tone,
                        "status": drafts[e.id].status.value,
                        "auto_decision": drafts[e.id].auto_decision,
                        "sent_at": _iso(drafts[e.id].sent_at),
                    }
                    if e.id in drafts
                    else None
                ),
                "actions": [
                    {
                        "id": str(a.id),
                        "type": a.type.value,
                        "description": a.description,
                        "due": _iso(a.due),
                        "contact": a.contact,
                        "property": a.property,
                        "status": a.status.value,
                    }
                    for a in actions.values()
                    if a.email_id == e.id
                ],
            }
            for e in emails
        ],
    }


@router.get("/digest/{user_id}")
async def daily_digest(
    user_id: uuid.UUID,
    hours: int = 24,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Build the morning brief from threads active in the last `hours` + open actions."""
    ensure_self(user, user_id)
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

    brief = digest.build_digest(threads, actions)
    return {
        "generated_at": now.isoformat(),
        "window_hours": hours,
        "threads_in_window": len(threads),
        "actions_in_window": len(actions),
        **brief,
    }


@router.get("/action-items/{user_id}")
async def action_items(
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    result = await db.execute(
        select(models.ActionItem)
        .join(models.Email)
        .join(models.Thread)
        .where(
            models.Thread.user_id == user_id,
            models.ActionItem.status == models.ActionStatus.open,
        )
        .order_by(models.ActionItem.created_at.desc())
    )
    return {
        "action_items": [
            {
                "id": str(a.id),
                "type": a.type.value,
                "description": a.description,
                "due": _iso(a.due),
                "contact": a.contact,
                "property": a.property,
                "status": a.status.value,
            }
            for a in result.scalars().all()
        ]
    }