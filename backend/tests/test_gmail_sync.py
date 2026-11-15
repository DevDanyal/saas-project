import base64
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base
from app.services import gmail_sync


class _Resp:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Threads:
    def __init__(self, items, details):
        self._items = items
        self._details = details

    def list(self, **kwargs):
        return _Resp({"threads": self._items})

    def get(self, **kwargs):
        return _Resp(self._details[kwargs["id"]])


class _Messages:
    def __init__(self, read_ids):
        self._read_ids = read_ids

    def list(self, **kwargs):
        return _Resp({"messages": [{"id": mid} for mid in self._read_ids]})


class FakeGmail:
    def __init__(self, items, details, read_ids=None):
        self._threads = _Threads(items, details)
        self._messages = _Messages(read_ids or [])

    def users(self):
        return self

    def threads(self):
        return self._threads

    def messages(self):
        return self._messages


def _text_payload(text):
    return {
        "mimeType": "text/plain",
        "body": {"data": base64.urlsafe_b64encode(text.encode()).decode()},
    }


def _msg(mid, subject, frm, to, date, body, attachment=False, labels=None):
    payload = _text_payload(body)
    msg = {
        "id": mid,
        "labelIds": labels or [],
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": frm},
                {"name": "To", "value": to},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": date},
                {"name": "Message-ID", "value": f"<{mid}@gmail>"},
            ],
        },
    }
    if attachment:
        msg["payload"]["body"] = {"attachmentId": "abc"}
    else:
        msg["payload"]["parts"] = [payload]
    return msg


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_sync_ingests_emails(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    account = await crud.add_email_account(
        db, user.id, models.ProviderType.gmail, "agent@example.com",
        token_cache=json.dumps({"token": "fake"}),
    )
    assert account.id

    thread_id = "thread-1"
    messages = [
        _msg("msg-1", "Looking for a home", "buyer@example.com",
             "agent@example.com", "Sat, 20 Sep 2026 09:00:00 +0000",
             "We are pre-approved for $450k."),
        _msg("msg-2", "Looking for a home", "agent@example.com",
             "buyer@example.com", "Sat, 20 Sep 2026 10:00:00 +0000",
             "That sounds great, let us schedule a tour."),
    ]
    details = {thread_id: {"id": thread_id, "messages": messages}}
    fake = FakeGmail([{"id": thread_id}], details)

    stats = await gmail_sync.sync_user_inbox(db, user.id, service=fake)

    assert stats["threads"] == 1
    assert stats["emails_added"] == 2
    assert stats["emails_skipped"] == 0

    threads = await crud.list_threads_for_user(db, user.id)
    assert len(threads) == 1
    assert threads[0].subject == "Looking for a home"

    emails = await crud.list_emails_for_thread(db, threads[0].id)
    assert len(emails) == 2
    assert emails[1].from_addr == "buyer@example.com"
    assert emails[1].body == "We are pre-approved for $450k."

    second = await gmail_sync.sync_user_inbox(db, user.id, service=fake)
    assert second["emails_added"] == 0
    assert second["emails_skipped"] == 2


@pytest.mark.asyncio
async def test_sync_raises_without_account(db):
    user = await crud.get_or_create_user(db, "Agent", "nobody@example.com")
    with pytest.raises(ValueError):
        await gmail_sync.sync_user_inbox(db, user.id, service=FakeGmail([], {}))


@pytest.mark.asyncio
async def test_sync_keeps_read_state_in_sync(db):
    user = await crud.get_or_create_user(db, "Agent", "reader@example.com")
    await crud.add_email_account(
        db, user.id, models.ProviderType.gmail, "reader@example.com",
        token_cache=json.dumps({"token": "fake"}),
    )

    thread_id = "thread-read"
    unread = _msg(
        "msg-unread", "New lead", "buyer@example.com", "reader@example.com",
        "Sat, 20 Sep 2026 09:00:00 +0000", "Interested in a showing.",
        labels=["UNREAD", "INBOX"],
    )
    fake = FakeGmail([{"id": thread_id}], {thread_id: {"id": thread_id, "messages": [unread]}})

    await gmail_sync.sync_user_inbox(db, user.id, service=fake)
    thread = (await crud.list_threads_for_user(db, user.id))[0]
    email = (await crud.list_emails_for_thread(db, thread.id))[0]
    assert email.is_read is False

    # Same message, now read in Gmail: re-sync should update local state.
    read = _msg(
        "msg-unread", "New lead", "buyer@example.com", "reader@example.com",
        "Sat, 20 Sep 2026 09:00:00 +0000", "Interested in a showing.",
        labels=["INBOX"],
    )
    fake2 = FakeGmail([{"id": thread_id}], {thread_id: {"id": thread_id, "messages": [read]}})
    stats = await gmail_sync.sync_user_inbox(db, user.id, service=fake2)

    assert stats["emails_added"] == 0
    await db.refresh(email)
    assert email.is_read is True

    # Locally read mail must not be resurrected from Gmail's UNREAD label,
    # since we can't write labels back with gmail.readonly.
    again = FakeGmail([{"id": thread_id}], {thread_id: {"id": thread_id, "messages": [unread]}})
    await gmail_sync.sync_user_inbox(db, user.id, service=again)
    await db.refresh(email)
    assert email.is_read is True


@pytest.mark.asyncio
async def test_sync_folds_gmail_read_state_for_older_threads(db):
    user = await crud.get_or_create_user(db, "Agent", "reads@example.com")
    await crud.add_email_account(
        db, user.id, models.ProviderType.gmail, "reads@example.com",
        token_cache=json.dumps({"token": "fake"}),
    )
    thread = await crud.upsert_thread(db, user.id, "thread-old", "Old mail")
    email = await crud.insert_email(
        db, thread.id, "msg-old", "buyer@example.com", "reads@example.com",
        "Old mail", "Read in Gmail later.", datetime.now(timezone.utc),
        is_read=False,
    )

    # The message is no longer in the recent thread page, but Gmail reports
    # it as read, so the local row must follow.
    fake = FakeGmail([], {}, read_ids=["msg-old"])
    stats = await gmail_sync.sync_user_inbox(db, user.id, service=fake)

    await db.refresh(email)
    assert email.is_read is True
    assert stats["marked_read"] == 1