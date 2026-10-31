import base64
import email.utils
import json
from datetime import datetime, timezone
from uuid import UUID

from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.services import crypto, gmail_auth, gmail_send


def account_can_send(account: models.EmailAccount | None) -> bool:
    return account is not None and gmail_auth.scope_allows(account.scope, gmail_auth.SEND_SCOPE)


def _credentials_from_account(account: models.EmailAccount) -> Credentials:
    token_json = crypto.decrypt_text(account.token_cache or "")
    if not token_json:
        raise ValueError("No stored credentials for account")
    return Credentials.from_authorized_user_info(json.loads(token_json), scopes=gmail_auth.SCOPES)


def _extract_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = (payload.get("body") or {}).get("data") or ""
        try:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        except Exception:
            return ""
    text = ""
    for part in payload.get("parts", []) or []:
        text += _extract_text(part) or ""
    return text


def _has_attachment(payload: dict) -> bool:
    if (payload.get("body") or {}).get("attachmentId"):
        return True
    return any(_has_attachment(p) for p in (payload.get("parts") or []))


def _header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_date(value: str) -> datetime:
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt is None:
            return datetime.now(timezone.utc)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


async def sync_user_inbox(
    db: AsyncSession, user_id: UUID, service=None, max_results: int = 20
) -> dict:
    account = await crud.get_email_account(db, user_id, models.ProviderType.gmail)
    if account is None:
        raise ValueError("No Gmail account connected")

    if service is None:
        creds = _credentials_from_account(account)
        service = gmail_auth.build_gmail_service(creds)

    thread_result = service.users().threads().list(
        userId="me", maxResults=max_results
    ).execute()

    stats = {"threads": 0, "emails_added": 0, "emails_skipped": 0, "errors": 0}

    for item in thread_result.get("threads", []):
        try:
            thread_data = service.users().threads().get(
                userId="me", id=item["id"], format="full"
            ).execute()
            messages = thread_data.get("messages", [])
            if not messages:
                stats["errors"] += 1
                continue

            subject = _header(messages[0], "Subject")
            dates = [_parse_date(_header(m, "Date")) for m in messages]
            thread = await crud.upsert_thread(
                db, user_id, item["id"], subject, last_activity_at=max(dates)
            )

            for msg in messages:
                mid = msg.get("id")
                if not mid:
                    continue
                if await crud.get_email_by_message_id(db, mid) is not None:
                    stats["emails_skipped"] += 1
                    continue

                payload = msg.get("payload", {})
                body = _extract_text(payload) or msg.get("snippet", "")
                await crud.insert_email(
                    db, thread.id, mid,
                    _header(msg, "From"), _header(msg, "To"),
                    _header(msg, "Subject"), body,
                    _parse_date(_header(msg, "Date")),
                    has_attachment=_has_attachment(payload),
                )
                stats["emails_added"] += 1

            stats["threads"] += 1
        except Exception:
            stats["errors"] += 1

    await db.flush()
    return stats


def _reply_subject(subject: str) -> str:
    subject = (subject or "").strip()
    if not subject:
        return "Re: (no subject)"
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


async def send_draft_reply(
    db: AsyncSession,
    draft_id,
    text: str | None = None,
    service=None,
) -> dict:
    """Send an AI draft as a reply, then mark it sent. Raises on failure."""
    draft = await db.get(models.AiDraft, draft_id)
    if draft is None:
        raise ValueError("Draft not found")
    if draft.status == models.DraftStatus.sent:
        raise ValueError("Draft has already been sent")

    email = await db.get(models.Email, draft.email_id)
    if email is None:
        raise ValueError("Draft has no source email")
    thread = await db.get(models.Thread, email.thread_id)
    if thread is None:
        raise ValueError("Draft has no thread")

    account = await crud.get_email_account(db, thread.user_id, models.ProviderType.gmail)
    if account is None:
        raise ValueError("No Gmail account connected")

    body_text = text if text is not None else draft.text

    if service is None:
        if not account_can_send(account):
            raise PermissionError(
                "Gmail send permission not granted. Reconnect Gmail to allow replies."
            )
        creds = _credentials_from_account(account)
        service = gmail_auth.build_gmail_service(creds)

    result = gmail_send.send_reply(
        service,
        to_addr=email.from_addr,
        subject=_reply_subject(email.subject),
        body=body_text,
        thread_id=thread.thread_id,
        from_addr=account.email,
    )

    draft.text = body_text
    draft.status = models.DraftStatus.sent
    draft.sent_message_id = result.get("id")
    draft.sent_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "draft_id": str(draft.id),
        "status": draft.status.value,
        "sent_message_id": draft.sent_message_id,
        "to": email.from_addr,
        "subject": _reply_subject(email.subject),
    }