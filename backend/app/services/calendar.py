"""Google Calendar integration (Phase 4).

Creates events from extracted action items and checks availability. Uses the
same stored OAuth credentials as Gmail; callers must have granted the
``calendar.events`` scope (reconnect Gmail after upgrading).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from google.oauth2.credentials import Credentials

from app.db import crud, models
from app.services import crypto, gmail_auth

logger = logging.getLogger(__name__)

CALENDAR_SCOPE = gmail_auth.CALENDAR_SCOPE


def _credentials_from_account(account: models.EmailAccount) -> Credentials:
    token_json = crypto.decrypt_text(account.token_cache or "")
    if not token_json:
        raise ValueError("No stored credentials for account")
    return Credentials.from_authorized_user_info(
        json.loads(token_json), scopes=gmail_auth.SCOPES
    )


async def _account_for(db, user_id) -> models.EmailAccount:
    account = await crud.get_email_account(db, user_id, models.ProviderType.gmail)
    if account is None:
        raise ValueError("No Gmail account connected")
    if not gmail_auth.scope_allows(account.scope, CALENDAR_SCOPE):
        raise PermissionError("Calendar access not granted; reconnect Gmail")
    return account


async def create_event(
    db,
    user_id: UUID,
    *,
    summary: str,
    start: datetime,
    end: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    timezone_name: str = "UTC",
    service=None,
) -> dict:
    account = await _account_for(db, user_id)
    if service is None:
        service = gmail_auth.build_calendar_service(_credentials_from_account(account))
    if end is None:
        end = start + timedelta(hours=1)

    body: dict = {
        "summary": summary or "Smart Inbox action",
        "description": description or "",
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees if a]

    event = service.events().insert(calendarId="primary", body=body).execute()
    return {
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "status": "created",
    }


async def check_availability(
    db,
    user_id: UUID,
    time_min: datetime,
    time_max: datetime,
    service=None,
) -> dict:
    account = await _account_for(db, user_id)
    if service is None:
        service = gmail_auth.build_calendar_service(_credentials_from_account(account))
    body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = (result.get("calendars", {}).get("primary", {}) or {}).get("busy", [])
    return {"busy": busy, "available": len(busy) == 0}


async def propose_time_slot(
    db,
    user_id: UUID,
    *,
    duration_minutes: int = 60,
    days_ahead: int = 7,
    service=None,
) -> dict | None:
    """Find the next free weekday slot between 09:00 and 17:00 UTC."""
    account = await _account_for(db, user_id)
    if service is None:
        service = gmail_auth.build_calendar_service(_credentials_from_account(account))

    time_min = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    time_max = time_min + timedelta(days=days_ahead)
    busy = await check_availability(db, user_id, time_min, time_max, service=service)

    busy_ranges = []
    for slot in busy["busy"]:
        try:
            busy_ranges.append(
                (
                    datetime.fromisoformat(slot["start"].replace("Z", "+00:00")),
                    datetime.fromisoformat(slot["end"].replace("Z", "+00:00")),
                )
            )
        except (KeyError, ValueError):
            continue

    cursor = time_min
    while cursor < time_max:
        if cursor.weekday() < 5 and 9 <= cursor.hour < 17:
            candidate_end = cursor + timedelta(minutes=duration_minutes)
            conflict = any(
                cursor < b_end and candidate_end > b_start
                for b_start, b_end in busy_ranges
            )
            if not conflict:
                return {
                    "start": cursor.isoformat(),
                    "end": candidate_end.isoformat(),
                }
        cursor += timedelta(minutes=30)
    return None
