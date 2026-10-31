"""Email deliverability utilities - SPF/DKIM/DMARC, unsubscribe, bounce handling."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud, models


UNSUBSCRIBE_SECRET = (
    settings.encryption_key[:32].encode()
    if settings.encryption_key
    else secrets.token_bytes(32)
)


def generate_unsubscribe_token(email: str, user_id: str) -> str:
    """Generate a secure unsubscribe token for a user."""
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    message = f"{user_id}:{email}:{timestamp}".encode()
    signature = hmac.new(UNSUBSCRIBE_SECRET, message, hashlib.sha256).hexdigest()[:16]
    return f"{timestamp}.{signature}"


def verify_unsubscribe_token(token: str, email: str, user_id: str, max_age_days: int = 365) -> bool:
    """Verify an unsubscribe token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        timestamp_str, signature = parts
        timestamp = int(timestamp_str)

        if datetime.now(timezone.utc) - datetime.fromtimestamp(timestamp, tz=timezone.utc) > timedelta(days=max_age_days):
            return False

        message = f"{user_id}:{email}:{timestamp_str}".encode()
        expected = hmac.new(UNSUBSCRIBE_SECRET, message, hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def build_unsubscribe_url(email: str, user_id: str) -> str:
    """Build the unsubscribe URL for email footers."""
    token = generate_unsubscribe_token(email, user_id)
    return f"{settings.frontend_url}/unsubscribe?email={quote(email)}&user_id={user_id}&token={token}"


async def handle_unsubscribe(db: AsyncSession, email: str, user_id: str, token: str) -> dict:
    """Process an unsubscribe request."""
    if not verify_unsubscribe_token(token, email, user_id):
        return {"success": False, "error": "Invalid or expired unsubscribe token"}

    import uuid as uuid_lib
    try:
        user_uuid = uuid_lib.UUID(user_id)
    except ValueError:
        return {"success": False, "error": "Invalid user ID"}

    account = await crud.get_email_account(db, user_uuid, models.ProviderType.gmail)
    if account:
        account.is_active = False
        await db.commit()

    return {"success": True, "message": "Successfully unsubscribed"}


def add_unsubscribe_headers(email_addr: str, user_id: str) -> dict:
    """Generate List-Unsubscribe headers for outgoing emails."""
    unsubscribe_url = build_unsubscribe_url(email_addr, user_id)
    return {
        "List-Unsubscribe": f"<{unsubscribe_url}>, <mailto:unsubscribe@{settings.frontend_url.replace('https://', '').replace('http://', '')}?subject=unsubscribe&body={quote(email_addr)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


async def process_bounce(db: AsyncSession, bounce_data: dict) -> dict:
    """Process a bounce notification from email provider."""
    email = bounce_data.get("email")
    bounce_type = bounce_data.get("type")  # hard, soft, spam, etc.
    reason = bounce_data.get("reason", "")

    if not email:
        return {"success": False, "error": "Missing email in bounce data"}

    if bounce_type == "hard":
        await crud.deactivate_email_account(db, email)
        return {"success": True, "action": "deactivated", "reason": "Hard bounce"}

    elif bounce_type == "spam":
        await crud.deactivate_email_account(db, email)
        return {"success": True, "action": "deactivated", "reason": "Spam complaint"}

    elif bounce_type == "soft":
        return {"success": True, "action": "retry", "reason": reason}

    return {"success": True, "action": "logged", "reason": reason}


def validate_spf_dkim_dmarc(domain: str) -> dict:
    """Validate SPF/DKIM/DMARC records for a domain (placeholder for production)."""
    import dns.resolver

    results = {"spf": None, "dkim": None, "dmarc": None}

    try:
        spf_records = dns.resolver.resolve(domain, "TXT")
        for record in spf_records:
            if "v=spf1" in str(record):
                results["spf"] = str(record)
                break
    except Exception:
        pass

    try:
        dmarc_records = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        for record in dmarc_records:
            if "v=DMARC1" in str(record):
                results["dmarc"] = str(record)
                break
    except Exception:
        pass

    return results


def generate_email_preview_text(body: str, max_length: int = 100) -> str:
    """Generate preview text for email clients."""
    text = " ".join(body.split())
    return text[:max_length] + ("..." if len(text) > max_length else "")