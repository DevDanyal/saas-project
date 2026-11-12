import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import ensure_self, require_user
from app.db import crud, models
from app.db.session import get_session
from app.services import billing

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    price_id: str
    mode: str = "subscription"


@router.post("/checkout/{user_id}")
@limiter.limit("10/minute")
async def create_checkout(
    request: Request,
    user_id: uuid.UUID,
    body: CheckoutRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    try:
        url = await billing.create_checkout_session(db, str(user_id), body.price_id, body.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"url": url}


@router.post("/portal/{user_id}")
@limiter.limit("10/minute")
async def create_portal(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    try:
        url = await billing.create_portal_session(db, str(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"url": url}


@router.get("/subscription/{user_id}")
@limiter.limit("30/minute")
async def get_subscription(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    sub = await crud.get_active_subscription(db, user_id)
    if not sub:
        return {"plan": "free", "status": "inactive", "limits": billing.get_plan_limits(models.PlanType.free)}
    return {
        "plan": sub.plan.value,
        "status": sub.status.value,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "limits": billing.get_plan_limits(sub.plan),
    }


@router.get("/limits/{user_id}")
@limiter.limit("30/minute")
async def get_limits(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    sub = await crud.get_active_subscription(db, user_id)
    plan = sub.plan if sub else models.PlanType.free
    limits = billing.get_plan_limits(plan)
    can_process, usage = await billing.check_email_limit(db, str(user_id))
    return {"plan": plan.value, "limits": limits, "usage": usage, "can_process": can_process}


@router.post("/webhook")
@limiter.limit("100/minute")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_session),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    payload = await request.body()
    try:
        await billing.handle_webhook(payload, stripe_signature, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    return {"received": True}


@router.get("/prices")
@limiter.limit("30/minute")
async def get_prices(
    request: Request, user: models.User = Depends(require_user)
):
    prices = [
        {"price_id": settings.stripe_price_free, "name": "free", "monthly_price": 0},
        {"price_id": settings.stripe_price_pro, "name": "pro", "monthly_price": 29},
        {"price_id": settings.stripe_price_team, "name": "team", "monthly_price": 39},
    ]
    return {"prices": prices}


@router.post("/admin/purge-emails")
@limiter.limit("5/minute")
async def admin_purge_emails(
    request: Request,
    older_than: str = Query(..., description="ISO 8601 datetime cutoff"),
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete every email received before *older_than*. Admin only."""
    if user.role != models.RoleType.admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    try:
        older = datetime.fromisoformat(older_than)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="older_than must be an ISO 8601 datetime"
        )
    deleted = await crud.purge_old_emails(db, older)
    return {"deleted_emails": deleted, "older_than": older_than}