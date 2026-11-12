"""Public API (Phase 5) — read-only endpoints for external integrations.

Authentication: ``X-API-Key`` header matched against ``PUBLIC_API_KEYS`` (comma
separated). Only endpoints explicitly listed here are exposed.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/public/v1", tags=["public"])


def _require_api_key(request: Request) -> None:
    allowed = {k.strip() for k in (settings.public_api_keys or "").split(",") if k.strip()}
    if not allowed:
        raise HTTPException(status_code=503, detail="Public API is not configured")
    provided = request.headers.get("x-api-key", "")
    if provided not in allowed:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.get("/health")
async def public_health(request: Request):
    _require_api_key(request)
    return {"status": "ok"}


@router.get("/users/{user_id}/inbox-summary")
async def public_inbox_summary(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    _require_api_key(request)
    user = await crud.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    threads = await crud.list_threads_for_user(db, user_id, limit=50)
    from collections import Counter

    categories = Counter(t.category.value if t.category else "unknown" for t in threads)
    return {
        "user_id": str(user_id),
        "threads": len(threads),
        "unread_priority": [t.priority_score for t in threads if (t.priority_score or 0) >= 80],
        "categories": dict(categories),
    }
