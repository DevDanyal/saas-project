"""Session-cookie authentication.

Tokens are HMAC-signed, URL-safe strings stored in an HttpOnly cookie. No
server-side session store is required, so this works across stateless
backend replicas as long as SESSION_SECRET is shared.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud, models
from app.db.session import get_session

SESSION_COOKIE = "smart_inbox_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30


def _secret() -> bytes:
    secret = settings.session_secret or settings.encryption_key
    if not secret:
        raise RuntimeError("SESSION_SECRET (or ENCRYPTION_KEY) must be configured")
    return secret.encode()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_session_token(user_id: uuid.UUID | str) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + SESSION_MAX_AGE}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def decode_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64decode(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        sub = payload.get("sub")
        return str(sub) if sub else None
    except (ValueError, TypeError, KeyError):
        return None


def _cookie_secure() -> bool:
    return settings.frontend_url.startswith("https://")


def set_session_cookie(response: Response, user_id: uuid.UUID | str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="none" if _cookie_secure() else "lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="none" if _cookie_secure() else "lax",
    )


async def require_user(
    request: Request, db: AsyncSession = Depends(get_session)
) -> models.User:
    user_id = decode_session_token(request.cookies.get(SESSION_COOKIE))
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = await crud.get_user(db, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def ensure_self(user: models.User, user_id: uuid.UUID | str) -> None:
    if str(user.id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account",
        )
