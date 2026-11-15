import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic import BaseModel
from sqlalchemy import asc, desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.agents import pipeline, reply_drafter
from app.core.config import settings
from app.core.security import ensure_self, require_user
from app.db import crud, models
from app.db.session import get_session
from app.services import billing, digest_service, gmail_sync
from app.services.email_text import clean_email_body

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/emails", tags=["emails"])


class SendDraftRequest(BaseModel):
    text: str | None = None


class UpdateDraftRequest(BaseModel):
    text: str | None = None
    tone: str | None = None


class MarkReadRequest(BaseModel):
    is_read: bool = True


class UpdateActionItemRequest(BaseModel):
    status: Literal["open", "done", "cancelled"]


class UpdateThreadRequest(BaseModel):
    category: Literal[
        "lead", "client", "vendor", "legal", "financial", "internal", "spam", "newsletter"
    ] | None = None
    priority_score: int | None = Field(default=None, ge=0, le=100)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _thread_summary(
    t: models.Thread,
    *,
    email_count: int = 0,
    reply_status: str = "none",
    last_from: str | None = None,
    unread: int = 0,
) -> dict:
    return {
        "id": str(t.id),
        "subject": t.subject,
        "category": t.category.value if t.category else None,
        "priority_score": t.priority_score,
        "flags": t.flags or [],
        "pipeline_hints": t.pipeline_hints or [],
        "summary": t.summary,
        "last_activity_at": _iso(t.last_activity_at),
        "last_from": last_from,
        "reply_status": reply_status,
        "emails": email_count,
        "email_count": email_count,
        "unread": unread,
    }


def _reply_status_for(
    statuses: list[models.DraftStatus], category: models.CategoryType | None
) -> str:
    if models.DraftStatus.sent in statuses:
        return "replied"
    if any(s in (models.DraftStatus.draft, models.DraftStatus.edited) for s in statuses):
        return "draft_ready"
    if category in (models.CategoryType.client, models.CategoryType.lead):
        return "needs_reply"
    return "none"


async def _thread_meta_map(db: AsyncSession, threads: list[models.Thread]) -> dict:
    """Bulk-load email counts, latest sender, and reply status per thread."""
    thread_ids = [t.id for t in threads]
    meta: dict = {
        tid: {
            "emails": 0,
            "unread": 0,
            "last_from": None,
            "last_email_at": None,
            "draft_statuses": [],
        }
        for tid in thread_ids
    }
    if not thread_ids:
        return meta

    email_res = await db.execute(
        select(models.Email)
        .where(models.Email.thread_id.in_(thread_ids))
        .order_by(models.Email.received_at.asc())
    )
    emails = list(email_res.scalars().all())
    email_ids = [e.id for e in emails]

    latest_draft: dict = {}
    if email_ids:
        draft_res = await db.execute(
            select(models.AiDraft)
            .where(models.AiDraft.email_id.in_(email_ids))
            .order_by(models.AiDraft.created_at.asc())
        )
        for d in draft_res.scalars().all():
            latest_draft[d.email_id] = d

    for e in emails:
        m = meta.get(e.thread_id)
        if m is None:
            continue
        m["emails"] += 1
        if not e.is_read:
            m["unread"] += 1
        if m["last_email_at"] is None or (
            e.received_at is not None and e.received_at >= m["last_email_at"]
        ):
            m["last_email_at"] = e.received_at
            m["last_from"] = e.from_addr
        draft = latest_draft.get(e.id)
        if draft is not None:
            m["draft_statuses"].append(draft.status)

    for t in threads:
        m = meta[t.id]
        m["reply_status"] = _reply_status_for(m["draft_statuses"], t.category)
    return meta


@router.get("/stats/{user_id}")
@limiter.limit("60/minute")
async def inbox_stats(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Aggregate counts for inbox sections and the assistant summary."""
    ensure_self(user, user_id)
    threads = list(await crud.list_threads_for_user(db, user_id, limit=500))
    meta = await _thread_meta_map(db, threads)

    categories: dict[str, int] = {}
    reply_status = {"replied": 0, "draft_ready": 0, "needs_reply": 0, "none": 0}
    processed = 0
    attention = 0
    unread_threads = 0
    for t in threads:
        key = t.category.value if t.category else "uncategorized"
        categories[key] = categories.get(key, 0) + 1
        status = meta[t.id]["reply_status"]
        reply_status[status] = reply_status.get(status, 0) + 1
        if meta[t.id]["unread"]:
            unread_threads += 1
        if t.summary:
            processed += 1
        flags = set(t.flags or [])
        if (t.priority_score or 0) >= 85 or flags & {"hot_lead", "closing_deadline", "complaint"}:
            attention += 1

    return {
        "total": len(threads),
        "processed": processed,
        "unprocessed": len(threads) - processed,
        "customers": categories.get("client", 0),
        "leads": categories.get("lead", 0),
        "attention": attention,
        "pending_drafts": reply_status.get("draft_ready", 0),
        "unread": unread_threads,
        "categories": categories,
        "reply_status": reply_status,
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

    can_process, usage = await billing.check_email_limit(db, thread.user_id)
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
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"AI processing failed: {e}")
    await db.commit()
    return result


@router.patch("/{email_id}/read")
@limiter.limit("120/minute")
async def mark_email_read(
    request: Request,
    email_id: uuid.UUID,
    body: MarkReadRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Mark a single email read or unread."""
    email = await db.get(models.Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    thread = await db.get(models.Thread, email.thread_id)
    if thread is None or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Email not found")
    email.is_read = body.is_read
    await db.commit()
    return {"id": str(email.id), "is_read": email.is_read}


@router.post("/{email_id}/draft")
@limiter.limit("30/minute")
async def generate_draft(
    request: Request,
    email_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate (or refresh) just the AI reply draft for one email."""
    email = await db.get(models.Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    thread = await db.get(models.Thread, email.thread_id)
    if thread is None or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Email not found")

    thread_emails = await crud.list_emails_for_thread(db, thread.id)
    thread_emails.sort(key=lambda m: m.received_at)
    thread_dicts = [
        {
            "from_addr": m.from_addr,
            "received_at": m.received_at.isoformat() if m.received_at else "",
            "subject": m.subject,
            "body": m.body,
        }
        for m in thread_emails
    ]
    prefs = await crud.get_preferences(db, thread.user_id)
    try:
        reply = reply_drafter.draft_reply(
            thread_dicts,
            tone_profile=prefs.tone_profile if prefs else None,
            rules=prefs.rules if prefs else None,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI draft failed: {e}")
    text = (reply.get("reply_text") or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="AI did not return a reply draft")

    existing = await crud.get_draft_for_email(db, email.id)
    if existing is not None and existing.status == models.DraftStatus.sent:
        raise HTTPException(status_code=409, detail="This email already has a sent reply")
    if existing is not None:
        existing.text = text
        existing.tone = reply.get("suggested_tone", "")
        existing.status = models.DraftStatus.draft
        existing.auto_decision = None
        await db.commit()
        await db.refresh(existing)
        return _draft_dict(existing)

    draft = await crud.add_draft(
        db, email.id, text, tone=reply.get("suggested_tone", "")
    )
    await db.commit()
    await db.refresh(draft)
    return _draft_dict(draft)


@router.post("/process-all/{user_id}")
@limiter.limit("120/hour")
async def process_inbox(
    request: Request,
    user_id: uuid.UUID,
    limit: int = 8,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Run the AI pipeline over a small batch of unprocessed emails.

    The frontend calls this repeatedly until ``pending`` reaches zero so each
    request stays inside the serverless time limit.
    """
    ensure_self(user, user_id)
    can_process, usage = await billing.check_email_limit(db, user_id)
    if not can_process:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Monthly email processing limit reached",
                "usage": usage,
                "upgrade_url": f"{settings.frontend_url}/billing",
            },
        )

    limit = max(1, min(limit, 20))
    pending_filter = (
        models.Thread.user_id == user_id,
        models.Email.ai_summary.is_(None),
    )
    result = await db.execute(
        select(models.Email.id)
        .join(models.Thread)
        .where(*pending_filter)
        .order_by(models.Email.received_at.asc())
        .limit(limit)
    )
    email_ids = list(result.scalars().all())
    processed, errors, last_error = 0, 0, None
    for email_id in email_ids:
        can_process, _ = await billing.check_email_limit(db, user_id)
        if not can_process:
            break
        try:
            await pipeline.process_email(db, email_id)
            await db.commit()
            processed += 1
        except Exception as e:
            await db.rollback()
            errors += 1
            last_error = str(e)[:300]
    remaining = await db.scalar(
        select(func.count())
        .select_from(models.Email)
        .join(models.Thread)
        .where(*pending_filter)
    )
    return {
        "processed": processed,
        "errors": errors,
        "pending": remaining or 0,
        "last_error": last_error,
    }


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


async def _owned_draft(db: AsyncSession, draft_id, user_id) -> models.AiDraft:
    draft = await db.get(models.AiDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft_email = await db.get(models.Email, draft.email_id)
    draft_thread = (
        await db.get(models.Thread, draft_email.thread_id) if draft_email else None
    )
    if draft_thread is None or draft_thread.user_id != user_id:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _draft_dict(draft: models.AiDraft) -> dict:
    return {
        "id": str(draft.id),
        "email_id": str(draft.email_id),
        "text": draft.text,
        "tone": draft.tone,
        "status": draft.status.value,
        "auto_decision": draft.auto_decision,
        "sent_at": _iso(draft.sent_at),
    }


@router.patch("/drafts/{draft_id}")
@limiter.limit("60/minute")
async def update_draft(
    request: Request,
    draft_id: uuid.UUID,
    body: UpdateDraftRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Edit a draft before sending. Sent or rejected drafts are immutable."""
    draft = await _owned_draft(db, draft_id, user.id)
    if draft.status in (models.DraftStatus.sent, models.DraftStatus.rejected):
        raise HTTPException(status_code=409, detail="Draft can no longer be edited")
    if body.text is not None:
        draft.text = body.text
    if body.tone is not None:
        draft.tone = body.tone
    draft.status = models.DraftStatus.edited
    await db.commit()
    await db.refresh(draft)
    return _draft_dict(draft)


@router.post("/drafts/{draft_id}/reject")
@limiter.limit("60/minute")
async def reject_draft(
    request: Request,
    draft_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    draft = await _owned_draft(db, draft_id, user.id)
    if draft.status == models.DraftStatus.sent:
        raise HTTPException(status_code=409, detail="Draft already sent")
    draft.status = models.DraftStatus.rejected
    await db.commit()
    await db.refresh(draft)
    return _draft_dict(draft)


@router.get("/inbox/{user_id}")
@limiter.limit("60/minute")
async def inbox(
    request: Request,
    user_id: uuid.UUID,
    limit: int = 100,
    q: str | None = None,
    category: str | None = None,
    flag: str | None = None,
    unread: bool = False,
    min_priority: int | None = None,
    sort: Literal["priority", "recent", "subject"] = "priority",
    order: Literal["asc", "desc"] = "desc",
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    stmt = select(models.Thread).where(models.Thread.user_id == user_id)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                models.Thread.subject.ilike(needle),
                models.Thread.summary.ilike(needle),
            )
        )
    if category:
        try:
            stmt = stmt.where(models.Thread.category == models.CategoryType(category))
        except ValueError:
            raise HTTPException(status_code=422, detail="Unknown category")
    if min_priority is not None:
        stmt = stmt.where(models.Thread.priority_score >= min_priority)
    if unread:
        stmt = stmt.where(
            exists().where(
                models.Email.thread_id == models.Thread.id,
                models.Email.is_read.is_(False),
            )
        )

    sort_column = {
        "priority": models.Thread.priority_score,
        "recent": models.Thread.last_activity_at,
        "subject": models.Thread.subject,
    }[sort]
    direction = asc if order == "asc" else desc
    stmt = stmt.order_by(direction(sort_column).nulls_last()).limit(limit)

    threads = list((await db.execute(stmt)).scalars().all())
    if flag:
        threads = [t for t in threads if flag in (t.flags or [])]
    meta = await _thread_meta_map(db, threads)
    return {
        "threads": [
            _thread_summary(
                t,
                email_count=meta[t.id]["emails"],
                reply_status=meta[t.id]["reply_status"],
                last_from=meta[t.id]["last_from"],
                unread=meta[t.id]["unread"],
            )
            for t in threads
        ]
    }


@router.patch("/threads/{thread_id}")
@limiter.limit("120/minute")
async def update_thread(
    request: Request,
    thread_id: uuid.UUID,
    body: UpdateThreadRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    thread = await crud.get_thread_detail(db, thread_id)
    if thread is None or thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Thread not found")
    if body.category is not None:
        thread.category = models.CategoryType(body.category)
    if body.priority_score is not None:
        thread.priority_score = body.priority_score
    await db.commit()
    await db.refresh(thread)
    return {
        "id": str(thread.id),
        "category": thread.category.value if thread.category else None,
        "priority_score": thread.priority_score,
    }


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

    reply_status = _reply_status_for(
        [d.status for d in drafts.values()], thread.category
    )

    return {
        **_thread_summary(
            thread,
            email_count=len(emails),
            reply_status=reply_status,
            last_from=emails[0].from_addr if emails else None,
            unread=sum(1 for e in emails if not e.is_read),
        ),
        "emails": [
            {
                "id": str(e.id),
                "from_addr": e.from_addr,
                "to_addr": e.to_addr,
                "subject": e.subject,
                "received_at": _iso(e.received_at),
                "body": clean_email_body(e.body),
                "ai_summary": e.ai_summary,
                "sentiment": e.sentiment,
                "has_attachment": e.has_attachment,
                "is_read": e.is_read,
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
    refresh: bool = False,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Return the morning brief from threads active in the last `hours` + open actions."""
    ensure_self(user, user_id)
    payload = await digest_service.get_or_build_digest(
        db, user_id, hours=hours, refresh=refresh
    )
    await db.commit()
    return payload


def _action_dict(a: models.ActionItem) -> dict:
    return {
        "id": str(a.id),
        "email_id": str(a.email_id),
        "type": a.type.value,
        "description": a.description,
        "due": _iso(a.due),
        "contact": a.contact,
        "property": a.property,
        "status": a.status.value,
    }


@router.get("/action-items/{user_id}")
async def action_items(
    user_id: uuid.UUID,
    status: Literal["open", "done", "cancelled", "all"] = "open",
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    stmt = (
        select(models.ActionItem)
        .join(models.Email)
        .join(models.Thread)
        .where(models.Thread.user_id == user_id)
        .order_by(models.ActionItem.created_at.desc())
    )
    if status != "all":
        stmt = stmt.where(models.ActionItem.status == models.ActionStatus(status))
    result = await db.execute(stmt)
    return {"action_items": [_action_dict(a) for a in result.scalars().all()]}


@router.patch("/action-items/{action_id}")
@limiter.limit("120/minute")
async def update_action_item(
    request: Request,
    action_id: uuid.UUID,
    body: UpdateActionItemRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    item = await db.get(models.ActionItem, action_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Action item not found")
    item_email = await db.get(models.Email, item.email_id)
    item_thread = (
        await db.get(models.Thread, item_email.thread_id) if item_email else None
    )
    if item_thread is None or item_thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Action item not found")
    item.status = models.ActionStatus(body.status)
    await db.commit()
    await db.refresh(item)
    return _action_dict(item)
