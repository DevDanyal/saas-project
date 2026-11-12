import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import ensure_self, require_user
from app.db import crud, models
from app.db.session import get_session
from app.services import calendar as calendar_service
from app.mcp import knowledge as knowledge_mcp
from app.mcp import lead_intel as lead_intel_mcp

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/integrations", tags=["integrations"])


class CalendarEventRequest(BaseModel):
    user_id: uuid.UUID
    summary: str
    start: datetime
    end: datetime | None = None
    description: str | None = None
    location: str | None = None
    attendees: list[str] | None = None
    timezone_name: str = "UTC"


class ProposeSlotRequest(BaseModel):
    user_id: uuid.UUID
    duration_minutes: int = 60
    days_ahead: int = 7


class TemplateRequest(BaseModel):
    name: str
    subject: str = ""
    body: str = ""


class DecisionRequest(BaseModel):
    key: str
    decision: object


@router.post("/calendar/events")
@limiter.limit("30/minute")
async def create_calendar_event(
    request: Request,
    body: CalendarEventRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, body.user_id)
    try:
        return await calendar_service.create_event(
            db,
            body.user_id,
            summary=body.summary,
            start=body.start,
            end=body.end,
            description=body.description,
            location=body.location,
            attendees=body.attendees,
            timezone_name=body.timezone_name,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/calendar/propose-slot")
@limiter.limit("30/minute")
async def propose_calendar_slot(
    request: Request,
    body: ProposeSlotRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, body.user_id)
    try:
        slot = await calendar_service.propose_time_slot(
            db,
            body.user_id,
            duration_minutes=body.duration_minutes,
            days_ahead=body.days_ahead,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if slot is None:
        raise HTTPException(status_code=404, detail="No free slot found")
    return slot


@router.get("/calendar/availability")
@limiter.limit("30/minute")
async def calendar_availability(
    request: Request,
    user_id: uuid.UUID,
    time_min: datetime,
    time_max: datetime,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    try:
        return await calendar_service.check_availability(db, user_id, time_min, time_max)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/knowledge/{user_id}/preferences")
@limiter.limit("60/minute")
async def knowledge_preferences(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    return await knowledge_mcp.get_agent_preferences(db, user_id)


@router.get("/knowledge/{user_id}/tone")
@limiter.limit("60/minute")
async def knowledge_tone(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    return {"tone_profile": await knowledge_mcp.get_tone_profile(db, user_id)}


@router.get("/knowledge/{user_id}/templates")
@limiter.limit("60/minute")
async def knowledge_templates(
    request: Request,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    return {"templates": await knowledge_mcp.get_response_templates(db, user_id)}


@router.post("/knowledge/{user_id}/templates")
@limiter.limit("30/minute")
async def knowledge_save_template(
    request: Request,
    user_id: uuid.UUID,
    body: TemplateRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    await knowledge_mcp.save_response_template(
        db, user_id, body.name, {"name": body.name, "subject": body.subject, "body": body.body}
    )
    await db.commit()
    return {"success": True}


@router.post("/knowledge/{user_id}/decisions")
@limiter.limit("30/minute")
async def knowledge_remember(
    request: Request,
    user_id: uuid.UUID,
    body: DecisionRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    ensure_self(user, user_id)
    result = await knowledge_mcp.remember_decision(db, user_id, body.key, body.decision)
    await db.commit()
    return result


@router.get("/lead-intel/listing")
@limiter.limit("60/minute")
async def lead_intel_listing(
    request: Request,
    address: str = Query(...),
    user: models.User = Depends(require_user),
):
    return await lead_intel_mcp.lookup_listing(address)


@router.get("/lead-intel/price-history")
@limiter.limit("60/minute")
async def lead_intel_price_history(
    request: Request,
    address: str = Query(...),
    user: models.User = Depends(require_user),
):
    return await lead_intel_mcp.price_history(address)


@router.post("/action-items/{action_id}/calendar")
@limiter.limit("30/minute")
async def action_item_to_calendar(
    request: Request,
    action_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    item = await db.get(models.ActionItem, action_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Action item not found")
    item_email = await db.get(models.Email, item.email_id)
    item_thread = await db.get(models.Thread, item_email.thread_id) if item_email else None
    if item_thread is None or item_thread.user_id != user.id:
        raise HTTPException(status_code=404, detail="Action item not found")
    start = item.due or datetime.now(timezone.utc) + timedelta(hours=1)
    try:
        result = await calendar_service.create_event(
            db,
            user.id,
            summary=item.description,
            start=start,
            description=f"From email action item ({item.type.value})",
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    item.status = models.ActionStatus.done
    await db.commit()
    return result


@router.get("/lead-intel/market-alert")
@limiter.limit("60/minute")
async def lead_intel_market_alert(
    request: Request,
    zip_code: str = Query(..., alias="zip"),
    user: models.User = Depends(require_user),
):
    return await lead_intel_mcp.market_alert(zip_code)
