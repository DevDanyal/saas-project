import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base
from app.services import billing, digest_service, gmail_auth


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def test_digest_falls_back_when_llm_fails():
    class BrokenLlm:
        def __call__(self, *args, **kwargs):
            raise RuntimeError("provider down")

    payload = digest_service.build_digest_payload(
        threads=[
            {"subject": "Hot buyer", "priority_score": 95, "flags": ["hot_lead"]},
            {"subject": "Closing soon", "priority_score": 70, "flags": ["closing_deadline"]},
        ],
        actions=[{"type": "follow_up", "description": "Call back"}],
        llm=BrokenLlm(),
    )

    assert "hot leads" in payload["brief"]
    assert payload["sections"]["hot_leads"] == ["Hot buyer"]
    assert payload["sections"]["closings"] == ["Closing soon"]
    assert payload["sections"]["follow_ups"] == ["Call back"]
    assert payload["threads_in_window"] == 2


def test_oauth_state_roundtrip_and_tamper():
    state = gmail_auth.create_oauth_state()
    assert gmail_auth.verify_oauth_state(state) is True

    body, sig = state.rsplit(".", 1)
    assert gmail_auth.verify_oauth_state(f"{body}.{'0' * len(sig)}") is False
    assert gmail_auth.verify_oauth_state(state + "x") is False
    assert gmail_auth.verify_oauth_state(None) is False
    assert gmail_auth.verify_oauth_state("not-a-state") is False


@pytest.mark.asyncio
async def test_billing_resolves_user_from_existing_subscription(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    await crud.upsert_subscription(
        db,
        user.id,
        plan=models.PlanType.pro,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        status=models.SubscriptionStatus.active,
    )
    await db.commit()

    assert await billing._resolve_user_id(db, "cus_123") == user.id
    assert await billing._resolve_user_id(db, "cus_missing") is None
    metadata = {"user_id": str(user.id)}
    assert await billing._resolve_user_id(db, "cus_missing", metadata) == user.id
    assert await billing._resolve_user_id(db, None, {"user_id": "nope"}) is None
    assert str(uuid.uuid4()) != str(user.id)
