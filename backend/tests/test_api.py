import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import SESSION_COOKIE, create_session_token
from app.db import crud, models
from app.db.base import Base
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)

    async with factory() as db:
        now = datetime.now(timezone.utc)
        user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
        thread = await crud.upsert_thread(
            db, user.id, "ext-1", "Lakefront buyer", last_activity_at=now,
            category=models.CategoryType.lead, priority_score=92,
            flags=["hot_lead"], summary="Pre-approved buyer wants lakefront homes.",
        )
        email = await crud.insert_email(
            db, thread.id, "msg-1", "buyer@example.com", "agent@example.com",
            "Lakefront buyer", "We are pre-approved for $450k.",
            now, ai_summary="Pre-approved buyer.",
            sentiment={"mood": "positive", "intensity": 0.8, "warning": False},
        )
        await crud.add_draft(db, email.id, "Happy to help you find a lakefront home!")
        await crud.add_action_item(
            db, email.id, models.ActionType.call, "Call re: showings", due=now,
            contact="buyer@example.com", property="lakefront",
        )
        await crud.add_notification(
            db, user.id, models.NotificationType.hot_lead, "Hot lead",
            "Pre-approved buyer", thread_id=thread.id, email_id=email.id,
        )
        db.add(models.AgentPreference(user_id=user.id, auto_features={}, tone_profile={}))
        await db.commit()

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={SESSION_COOKIE: create_session_token(user.id)},
    ) as client:
        yield client, user, thread

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_inbox_lists_threads(ctx):
    client, user, _ = ctx
    r = await client.get(f"/emails/inbox/{user.id}")
    assert r.status_code == 200
    threads = r.json()["threads"]
    assert len(threads) == 1
    assert threads[0]["category"] == "lead"
    assert threads[0]["priority_score"] == 92


@pytest.mark.asyncio
async def test_thread_detail(ctx):
    client, _, thread = ctx
    r = await client.get(f"/emails/threads/{thread.id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["subject"] == "Lakefront buyer"
    email = detail["emails"][0]
    assert email["draft"]["text"].startswith("Happy to help")
    assert email["actions"][0]["type"] == "call"
    assert email["sentiment"]["mood"] == "positive"


@pytest.mark.asyncio
async def test_action_items_endpoint(ctx):
    client, user, _ = ctx
    r = await client.get(f"/emails/action-items/{user.id}")
    assert r.status_code == 200
    items = r.json()["action_items"]
    assert len(items) == 1
    assert items[0]["type"] == "call"
    assert items[0]["contact"] == "buyer@example.com"


@pytest.mark.asyncio
async def test_thread_404(ctx):
    client, _, _ = ctx
    r = await client.get(f"/emails/threads/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_process_missing_email_returns_404(ctx):
    client, _, _ = ctx
    r = await client.post(f"/emails/process/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_google_login_returns_consent_url(ctx, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "test-secret")
    client, _, _ = ctx
    r = await client.get("/auth/google")
    assert r.status_code == 200
    body = r.json()
    assert "accounts.google.com" in body["authorization_url"]
    assert body["state"]


@pytest.mark.asyncio
async def test_google_redirect_rejects_bad_code(ctx, monkeypatch):
    from app.api.routes import auth as auth_route

    def boom(code: str, state: str):
        raise RuntimeError("bad code")

    monkeypatch.setattr(auth_route.gmail_auth, "exchange_code", boom)
    client, _, _ = ctx
    r = await client.get("/auth/google/redirect?code=x&state=y")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_users_endpoint(ctx):
    client, user, _ = ctx
    r = await client.get("/users")
    assert r.status_code == 200
    users = r.json()["users"]
    assert len(users) == 1
    assert users[0]["id"] == str(user.id)
    assert users[0]["email"] == "agent@example.com"


@pytest.mark.asyncio
async def test_digest_endpoint(monkeypatch, ctx):
    client, user, _ = ctx

    def fake_build(threads, actions, llm=None):
        return {
            "brief": "One hot lead, one action due soon.",
            "sections": {"hot_leads": ["Lakefront buyer"], "closings": [], "follow_ups": [], "other": []},
        }

    monkeypatch.setattr("app.api.routes.emails.digest.build_digest", fake_build)
    r = await client.get(f"/emails/digest/{user.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["brief"] == "One hot lead, one action due soon."
    assert body["sections"]["hot_leads"] == ["Lakefront buyer"]
    assert body["threads_in_window"] == 1


@pytest.mark.asyncio
async def test_notifications_endpoint_and_mark_read(ctx):
    client, user, _ = ctx
    r = await client.get(f"/notifications/{user.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["unread_count"] == 1
    assert body["notifications"][0]["type"] == "hot_lead"

    note_id = body["notifications"][0]["id"]
    r = await client.post(f"/notifications/{note_id}/read")
    assert r.status_code == 200
    assert r.json()["is_read"] is True

    r = await client.get(f"/notifications/{user.id}?unread_only=true")
    assert r.json() == {"notifications": [], "unread_count": 0}


@pytest.mark.asyncio
async def test_preferences_update_toggles_autopilot(ctx):
    client, user, _ = ctx
    r = await client.put(
        f"/preferences/{user.id}",
        json={"autopilot": True, "autopilot_confidence": 0.95},
    )
    assert r.status_code == 200
    assert r.json()["auto_features"]["autopilot"] is True

    r = await client.get(f"/preferences/{user.id}")
    assert r.json()["auto_features"]["autopilot_confidence"] == 0.95


@pytest.mark.asyncio
async def test_send_draft_endpoint(ctx, monkeypatch):
    from app.api.routes import emails as emails_route

    async def fake_send(db, draft_id, text=None, service=None):
        return {
            "draft_id": str(draft_id),
            "status": "sent",
            "sent_message_id": "m1",
            "to": "buyer@example.com",
            "subject": "Re: Lakefront buyer",
        }

    monkeypatch.setattr(emails_route.gmail_sync, "send_draft_reply", fake_send)
    client, _, thread = ctx

    detail = await client.get(f"/emails/threads/{thread.id}")
    draft_id = detail.json()["emails"][0]["draft"]["id"]

    r = await client.post(f"/emails/drafts/{draft_id}/send", json={"text": "Updated reply"})
    assert r.status_code == 200
    assert r.json()["status"] == "sent"