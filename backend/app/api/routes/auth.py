from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import (
    clear_session_cookie,
    require_user,
    set_session_cookie,
)
from app.db import crud, models
from app.db.session import get_session
from app.services import crypto, gmail_auth

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


def _serialize_user(user: models.User, gmail_connected: bool = False) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "gmail_connected": gmail_connected,
    }


def _frontend(status: str, **params: str) -> RedirectResponse:
    query = "&".join(f"{k}={quote(v)}" for k, v in params.items())
    url = f"{settings.frontend_url}/?{status}=1"
    if query:
        url += f"&{query}"
    return RedirectResponse(url)


@router.get("/me")
async def current_user(
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    account = await crud.get_email_account(db, user.id, models.ProviderType.gmail)
    return _serialize_user(user, gmail_connected=account is not None)


@router.post("/logout")
async def logout():
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response


@router.get("/google")
@limiter.limit("10/minute")
async def google_login(request: Request):
    """Return the Google consent URL for the frontend to redirect the user to."""
    state, url = gmail_auth.begin_authorization()
    return {"authorization_url": url, "state": state}


@router.get("/google/redirect")
@limiter.limit("20/minute")
async def google_redirect(request: Request, code: str, state: str, db: AsyncSession = Depends(get_session)):
    try:
        credentials = gmail_auth.exchange_code(code, state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid OAuth code")

    profile_email = gmail_auth.get_profile_email(credentials) or "unknown@example.com"
    user = await crud.get_or_create_user(db, "Agent", profile_email)
    await db.commit()

    account = await crud.get_email_account(db, user.id, models.ProviderType.gmail)
    token_json = crypto.encrypt_text(credentials.to_json())
    granted = ",".join(credentials.scopes or gmail_auth.SCOPES)
    if account is None:
        await crud.add_email_account(
            db,
            user.id,
            models.ProviderType.gmail,
            profile_email,
            scope=granted,
            token_cache=token_json,
        )
    else:
        account.token_cache = token_json
        account.scope = granted
        account.is_active = True
    await db.commit()

    response = _frontend("connected", user_id=str(user.id), email=profile_email)
    set_session_cookie(response, user.id)
    return response