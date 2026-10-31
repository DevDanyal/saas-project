import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesUpdate(BaseModel):
    autopilot: bool | None = None
    autopilot_confidence: float | None = None
    tone_profile: dict | None = None
    rules: str | None = None


def _serialize(pref: models.AgentPreference | None) -> dict:
    if pref is None:
        return {"tone_profile": {}, "auto_features": {}, "rules": None}
    return {
        "tone_profile": pref.tone_profile or {},
        "auto_features": pref.auto_features or {},
        "rules": pref.rules,
    }


@router.get("/{user_id}")
async def get_preferences(user_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    pref = await crud.get_preferences(db, user_id)
    return _serialize(pref)


@router.put("/{user_id}")
async def update_preferences(
    user_id: uuid.UUID,
    body: PreferencesUpdate,
    db: AsyncSession = Depends(get_session),
):
    pref = await crud.get_preferences(db, user_id)
    if pref is None:
        pref = models.AgentPreference(user_id=user_id, auto_features={}, tone_profile={})
        db.add(pref)
        await db.flush()

    features = dict(pref.auto_features or {})
    if body.autopilot is not None:
        features["autopilot"] = body.autopilot
    if body.autopilot_confidence is not None:
        features["autopilot_confidence"] = max(0.0, min(1.0, body.autopilot_confidence))
    pref.auto_features = features

    if body.tone_profile is not None:
        pref.tone_profile = body.tone_profile
    if body.rules is not None:
        pref.rules = body.rules

    await db.commit()
    return _serialize(pref)
