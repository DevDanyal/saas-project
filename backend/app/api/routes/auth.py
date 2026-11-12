import logging
from urllib.parse import quote

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
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


class PasswordSignup(BaseModel):
    name: str = "Agent"
    email: str
    password: str


class PasswordLogin(BaseModel):
    email: str
    password: str


class PasswordForgot(BaseModel):
    email: str


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


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


@router.post("/signup")
@limiter.limit("10/minute")
async def signup(
    request: Request,
    body: PasswordSignup,
    db: AsyncSession = Depends(get_session),
):
    email = _normalize_email(body.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = await crud.get_user_by_email(db, email)
    if existing is not None:
        if existing.password_hash:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Sign in instead.",
            )
        raise HTTPException(
            status_code=409,
            detail=(
                "This email is already connected with Google. "
                "Use “Continue with Google” to sign in."
            ),
        )
    name = body.name.strip() or "Agent"
    user = await crud.create_user(db, name, email)
    user.password_hash = _hash_password(body.password)
    await db.commit()
    response = JSONResponse(_serialize_user(user, gmail_connected=False))
    set_session_cookie(response, user.id)
    return response


@router.post("/login")
@limiter.limit("20/minute")
async def login(
    request: Request,
    body: PasswordLogin,
    db: AsyncSession = Depends(get_session),
):
    user = await crud.get_user_by_email(db, _normalize_email(body.email))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.password_hash:
        raise HTTPException(
            status_code=400,
            detail=(
                "This account signs in with Google. "
                "Use “Continue with Google” instead."
            ),
        )
    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    account = await crud.get_email_account(db, user.id, models.ProviderType.gmail)
    response = JSONResponse(_serialize_user(user, gmail_connected=account is not None))
    set_session_cookie(response, user.id)
    return response


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: PasswordForgot,
):
    """Placeholder for the reset flow: responds honestly, never sends mail."""
    return {
        "message": (
            "Password reset is not enabled on this server yet. "
            "Contact your administrator to restore access."
        )
    }


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
    except Exception as e:
        logger.exception("OAuth exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid OAuth code: {e}")

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