import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ensure_self, require_user
from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(note: models.Notification) -> dict:
    return {
        "id": str(note.id),
        "type": note.type.value,
        "title": note.title,
        "body": note.body,
        "is_read": note.is_read,
        "thread_id": str(note.thread_id) if note.thread_id else None,
        "email_id": str(note.email_id) if note.email_id else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


@router.get("/{user_id}")
async def list_notifications(
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    notes = await crud.list_notifications(
        db, user_id, unread_only=unread_only, limit=limit
    )
    unread = await crud.list_notifications(db, user_id, unread_only=True, limit=1000)
    return {
        "notifications": [_serialize(n) for n in notes],
        "unread_count": len(unread),
    }


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    existing = await db.get(models.Notification, notification_id)
    if existing is None or existing.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    note = await crud.mark_notification_read(db, notification_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return _serialize(note)
