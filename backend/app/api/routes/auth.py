from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.db import crud, models
from app.db.session import get_session
from app.services import crypto, gmail_auth

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth/google", tags=["auth"])


def _frontend(status: str, **params: str) -> RedirectResponse:
    query = "&".join(f"{k}={quote(v)}" for k, v in params.items())
    url = f"{settings.frontend_url}/?{status}=1"
    if query:
        url += f"&{query}"
    return RedirectResponse(url)


@router.get("")
@limiter.limit("10/minute")
async def google_login(request: Request):
    """Return the Google consent URL for the frontend to redirect the user to."""
    state, url = gmail_auth.begin_authorization()
    return {"authorization_url": url, "state": state}


@router.get("/redirect")
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

    return _frontend("connected", user_id=str(user.id), email=profile_email)