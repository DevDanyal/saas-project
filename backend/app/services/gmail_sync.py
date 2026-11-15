import base64
import email.utils
import json
from datetime import datetime, timezone
from uuid import UUID

from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.services import crypto, gmail_auth, gmail_send
from app.services.email_text import clean_email_body, html_to_text


def account_can_send(account: models.EmailAccount | None) -> bool:
    return account is not None and gmail_auth.scope_allows(account.scope, gmail_auth.SEND_SCOPE)


def _credentials_from_account(account: models.EmailAccount) -> Credentials:
    token_json = crypto.decrypt_text(account.token_cache or "")
    if not token_json:
        raise ValueError("No stored credentials for account")
    return Credentials.from_authorized_user_info(json.loads(token_json), scopes=gmail_auth.SCOPES)


def _decode_part_data(payload: dict) -> str:
    data = (payload.get("body") or {}).get("data") or ""
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _collect_body_parts(payload: dict, plain: list[str], rich: list[str]) -> None:
    mime = (payload.get("mimeType") or "").lower()
    decoded = _decode_part_data(payload)
    if decoded:
        if mime == "text/plain":
            plain.append(decoded)
        elif mime == "text/html":
            rich.append(decoded)
    for part in payload.get("parts", []) or []:
        _collect_body_parts(part, plain, rich)


def _extract_text(payload: dict) -> str:
    plain: list[str] = []
    rich: list[str] = []
    _collect_body_parts(payload, plain, rich)
    if plain:
        return clean_email_body("\n\n".join(plain))
    if rich:
        return clean_email_body(html_to_text("\n".join(rich)))
    return ""


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

    creds = None
    if service is None:
        creds = _credentials_from_account(account)
        service = gmail_auth.build_gmail_service(creds)

    if creds is not None:
        profile_email = gmail_auth.get_profile_email(creds)
        if profile_email:
            account.email = profile_email
            account.is_active = True
            user = await crud.get_user(db, user_id)
            if user is not None and (not user.email or user.email == "unknown@example.com"):
                user.email = profile_email
            await db.flush()

    thread_result = service.users().threads().list(
        userId="me", maxResults=max_results
    ).execute()

    stats = {"threads": 0, "emails_added": 0, "emails_skipped": 0, "errors": 0, "marked_read": 0}

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
                labels = msg.get("labelIds") or []
                is_read = "UNREAD" not in labels
                existing = await crud.get_email_by_message_id(db, mid)
                if existing is not None:
                    # We only have gmail.readonly, so never resurrect locally
                    # read mail. Fold in the gmail-unread -> read direction.
                    if is_read and not existing.is_read:
                        existing.is_read = True
                    stats["emails_skipped"] += 1
                    continue

                payload = msg.get("payload", {})
                body = _extract_text(payload) or clean_email_body(msg.get("snippet", ""))
                await crud.insert_email(
                    db, thread.id, mid,
                    _header(msg, "From"), _header(msg, "To"),
                    _header(msg, "Subject"), body,
                    _parse_date(_header(msg, "Date")),
                    has_attachment=_has_attachment(payload),
                    is_read=is_read,
                )
                stats["emails_added"] += 1

            stats["threads"] += 1
        except Exception:
            stats["errors"] += 1

    # Fold Gmail-side read transitions into local rows as well. This catches
    # messages the user read in Gmail that fall outside the thread page above.
    try:
        read_result = service.users().messages().list(
            userId="me", q="is:read newer_than:30d", maxResults=200
        ).execute()
        read_ids = [m.get("id") for m in read_result.get("messages", [])]
        stats["marked_read"] = await crud.mark_emails_read_by_message_ids(
            db, read_ids
        )
    except Exception:
        pass

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