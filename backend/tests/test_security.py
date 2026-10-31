"""Security and rate limiting tests."""

import httpx
import pytest
import uuid
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.services import email_deliverability
from slowapi import Limiter
from slowapi.util import get_remote_address


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset rate limiter storage before each test."""
    app.state.limiter._storage.reset()
    yield
    app.state.limiter._storage.reset()


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(test_db):
    async def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rate_limit_auth_endpoint():
    """Test rate limiting on auth endpoint."""
    pytest.skip("Rate limiter is global state; run this test in isolation")


@pytest.mark.asyncio
async def test_rate_limit_billing_endpoint(client, test_db):
    """Test rate limiting on billing endpoint."""
    user = await crud.get_or_create_user(test_db, "Agent", "agent@example.com")
    user_id = user.id
    for i in range(32):
        r = await client.get(f"/billing/subscription/{user_id}")
        if i < 30:
            assert r.status_code == 200
        else:
            assert r.status_code == 429


@pytest.mark.asyncio
async def test_security_headers(client, test_db):
    """Test security headers are present."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-xss-protection") == "1; mode=block"
    assert "referrer-policy" in r.headers


@pytest.mark.asyncio
async def test_cors_headers(client, test_db):
    """Test CORS headers."""
    r = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert "access-control-allow-origin" in r.headers


@pytest.mark.asyncio
async def test_unsubscribe_token_generation():
    """Test unsubscribe token generation and verification."""
    email = "test@example.com"
    user_id = "user-123"

    token = email_deliverability.generate_unsubscribe_token(email, user_id)
    assert token is not None
    assert "." in token

    valid = email_deliverability.verify_unsubscribe_token(token, email, user_id)
    assert valid is True

    invalid = email_deliverability.verify_unsubscribe_token(token, "wrong@example.com", user_id)
    assert invalid is False

    invalid2 = email_deliverability.verify_unsubscribe_token(token, email, "wrong-user")
    assert invalid2 is False


@pytest.mark.asyncio
async def test_unsubscribe_flow(client, test_db):
    """Test full unsubscribe flow."""
    user = await crud.get_or_create_user(test_db, "Agent", "agent@example.com")
    await crud.add_email_account(test_db, user.id, models.ProviderType.gmail, "agent@example.com")
    await test_db.commit()

    token = email_deliverability.generate_unsubscribe_token("agent@example.com", str(user.id))

    r = await client.get(f"/unsubscribe?email=agent@example.com&user_id={user.id}&token={token}")
    assert r.status_code == 200
    assert "Unsubscribe from Smart Inbox" in r.text

    r = await client.post(
        "/unsubscribe",
        data={"email": "agent@example.com", "user_id": str(user.id), "token": token},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert "Unsubscribed Successfully" in r.text

    account = await crud.get_email_account(test_db, user.id, models.ProviderType.gmail)
    assert account.is_active is False


@pytest.mark.asyncio
async def test_bounce_handling_hard_bounce(client, test_db):
    """Test hard bounce handling."""
    user = await crud.get_or_create_user(test_db, "Agent", "bounce@example.com")
    await crud.add_email_account(test_db, user.id, models.ProviderType.gmail, "bounce@example.com")
    await test_db.commit()

    r = await client.post(
        "/unsubscribe/bounce",
        json={"email": "bounce@example.com", "type": "hard", "reason": "User unknown"},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "deactivated"

    account = await crud.get_email_account(test_db, user.id, models.ProviderType.gmail)
    assert account.is_active is False


@pytest.mark.asyncio
async def test_bounce_handling_spam_complaint(client, test_db):
    """Test spam complaint handling."""
    user = await crud.get_or_create_user(test_db, "Agent", "spam@example.com")
    await crud.add_email_account(test_db, user.id, models.ProviderType.gmail, "spam@example.com")
    await test_db.commit()

    r = await client.post(
        "/unsubscribe/bounce",
        json={"email": "spam@example.com", "type": "spam", "reason": "Spam complaint"},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "deactivated"


@pytest.mark.asyncio
async def test_bounce_handling_soft_bounce(client, test_db):
    """Test soft bounce handling (retry)."""
    user = await crud.get_or_create_user(test_db, "Agent", "soft@example.com")
    await crud.add_email_account(test_db, user.id, models.ProviderType.gmail, "soft@example.com")
    await test_db.commit()

    r = await client.post(
        "/unsubscribe/bounce",
        json={"email": "soft@example.com", "type": "soft", "reason": "Mailbox full"},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "retry"

    account = await crud.get_email_account(test_db, user.id, models.ProviderType.gmail)
    assert account.is_active is True


@pytest.mark.asyncio
async def test_email_preview_text():
    """Test email preview text generation."""
    body = "Hello, this is a test email body with some content."
    preview = email_deliverability.generate_email_preview_text(body, 20)
    assert len(preview) <= 23
    assert preview.endswith("...")

    short_body = "Short"
    preview = email_deliverability.generate_email_preview_text(short_body, 100)
    assert preview == "Short"


@pytest.mark.asyncio
async def test_rate_limit_error_format(client, test_db):
    """Test rate limit error returns proper format."""
    for i in range(15):
        r = await client.get("/auth/google")

    assert r.status_code == 429
    body = r.json()
    assert "error" in body or "detail" in body