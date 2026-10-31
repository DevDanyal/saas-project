import base64
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base
from app.services import gmail_auth, gmail_send, gmail_sync


class _Resp:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _SendMessages:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, **kwargs):
        self.sent.append(kwargs["body"])
        return _Resp({"id": "sent-1", "threadId": kwargs["body"].get("threadId")})


class FakeGmailSender:
    def __init__(self):
        self._messages = _SendMessages()

    def users(self):
        return self

    def messages(self):
        return self._messages


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_draft(db, scope: str):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    await crud.add_email_account(
        db, user.id, models.ProviderType.gmail, "agent@example.com",
        scope=scope, token_cache=json.dumps({"token": "fake"}),
    )
    thread = await crud.upsert_thread(db, user.id, "thread-9", "Question about the offer")
    email = await crud.insert_email(
        db, thread.id, "msg-9", "buyer@example.com", "agent@example.com",
        "Question about the offer", "Can you send the details?",
        datetime.now(timezone.utc),
    )
    return await crud.add_draft(db, email.id, "Here are the details.")


def test_build_raw_message_encodes_body():
    payload = gmail_send.build_raw_message("b@example.com", "Re: Hi", "Hello there")
    decoded = base64.urlsafe_b64decode(payload["raw"]).decode()
    assert "To: b@example.com" in decoded
    assert "Hello there" in decoded


@pytest.mark.asyncio
async def test_send_draft_reply_marks_sent(db):
    draft = await _seed_draft(db, gmail_auth.SEND_SCOPE)
    sender = FakeGmailSender()

    result = await gmail_sync.send_draft_reply(db, draft.id, text="Edited reply.", service=sender)

    assert result["status"] == "sent"
    assert result["to"] == "buyer@example.com"
    assert result["subject"] == "Re: Question about the offer"
    assert draft.status == models.DraftStatus.sent
    assert draft.text == "Edited reply."
    assert draft.sent_message_id == "sent-1"
    assert draft.sent_at is not None

    body = sender._messages.sent[0]
    decoded = base64.urlsafe_b64decode(body["raw"]).decode()
    assert "Edited reply." in decoded
    assert body["threadId"] == "thread-9"


@pytest.mark.asyncio
async def test_send_without_scope_raises_permission(db):
    draft = await _seed_draft(db, gmail_auth.READ_SCOPE)
    with pytest.raises(PermissionError):
        await gmail_sync.send_draft_reply(db, draft.id)


@pytest.mark.asyncio
async def test_send_twice_raises(db):
    draft = await _seed_draft(db, gmail_auth.SEND_SCOPE)
    await gmail_sync.send_draft_reply(db, draft.id, service=FakeGmailSender())
    with pytest.raises(ValueError):
        await gmail_sync.send_draft_reply(db, draft.id, service=FakeGmailSender())


@pytest.mark.asyncio
async def test_send_without_account_raises(db):
    user = await crud.get_or_create_user(db, "Agent", "solo@example.com")
    thread = await crud.upsert_thread(db, user.id, "thread-x", "Hi")
    email = await crud.insert_email(
        db, thread.id, "msg-x", "a@example.com", "solo@example.com",
        "Hi", "ping", datetime.now(timezone.utc),
    )
    draft = await crud.add_draft(db, email.id, "pong")
    with pytest.raises(ValueError):
        await gmail_sync.send_draft_reply(db, draft.id, service=FakeGmailSender())
