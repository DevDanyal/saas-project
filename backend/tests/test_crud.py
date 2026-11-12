from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base


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
async def test_user_and_account_flow(db):
    user = await crud.get_or_create_user(db, "Test Agent", "agent@example.com")
    assert user.email == "agent@example.com"
    assert user.role == models.RoleType.agent

    account = await crud.add_email_account(db, user.id, models.ProviderType.gmail, "agent@example.com")
    assert account.provider == models.ProviderType.gmail

    fetched = await crud.get_email_account(db, user.id, models.ProviderType.gmail)
    assert fetched is not None and fetched.id == account.id


@pytest.mark.asyncio
async def test_thread_email_draft_action_flow(db):
    user = await crud.get_or_create_user(db, "Test Agent", "agent@example.com")
    now = datetime.now(timezone.utc)

    thread = await crud.upsert_thread(
        db, user.id, "ext-gmail-thread-1", "Looking to buy near the lake",
        last_activity_at=now, category=models.CategoryType.lead, priority_score=92,
    )
    assert thread.priority_score == 92

    thread2 = await crud.upsert_thread(db, user.id, "ext-gmail-thread-1", "Updated subject")
    assert thread2.id == thread.id
    assert thread2.subject == "Updated subject"

    email = await crud.insert_email(
        db, thread.id, "msg-1", "buyer@example.com", "agent@example.com",
        "Looking to buy near the lake", "Hi, we are pre-approved for $450k.", now,
        ai_summary="Buyer seeking waterfront home, pre-approved.",
        sentiment={"mood": "happy", "intensity": 0.8, "warning": False},
    )
    assert email.message_id == "msg-1"

    draft = await crud.add_draft(db, email.id, "Hi there! Happy to help you find a lakefront home.")
    assert draft.status == models.DraftStatus.draft

    item = await crud.add_action_item(
        db, email.id, models.ActionType.call, "Call buyer re: showings", due=now,
        contact="buyer@example.com", property="lakefront homes",
    )
    assert item.type == models.ActionType.call

    emails = await crud.list_emails_for_thread(db, thread.id)
    assert len(emails) == 1

    threads = await crud.list_threads_for_user(db, user.id)
    assert len(threads) == 1
    assert threads[0].category == models.CategoryType.lead


@pytest.mark.asyncio
async def test_purge_old_emails_cascades_and_keeps_live_thread(db):
    from sqlalchemy import select

    user = await crud.get_or_create_user(db, "Test Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-purge", "Thread")
    old = datetime(2025, 1, 1, tzinfo=timezone.utc)
    new = datetime.now(timezone.utc)

    old_email = await crud.insert_email(
        db, thread.id, "msg-old", "a@example.com", "agent@example.com",
        "Old", "old body", old,
    )
    new_email = await crud.insert_email(
        db, thread.id, "msg-new", "b@example.com", "agent@example.com",
        "New", "new body", new,
    )
    await crud.add_draft(db, old_email.id, "old draft")
    await crud.add_action_item(db, old_email.id, models.ActionType.call, "old call")
    await crud.add_notification(
        db, user.id, models.NotificationType.hot_lead, "old note", email_id=old_email.id
    )
    await db.commit()

    deleted = await crud.purge_old_emails(db, datetime(2025, 6, 1, tzinfo=timezone.utc))
    assert deleted == 1

    remaining_emails = (await db.execute(select(models.Email))).scalars().all()
    assert [e.id for e in remaining_emails] == [new_email.id]
    assert (await db.execute(select(models.AiDraft))).scalars().all() == []
    assert (await db.execute(select(models.ActionItem))).scalars().all() == []
    assert (await db.execute(select(models.Notification))).scalars().all() == []
    assert await crud.get_thread_detail(db, thread.id) is not None

    await crud.purge_old_emails(db, datetime(2999, 1, 1, tzinfo=timezone.utc))
    assert (await db.execute(select(models.Email))).scalars().all() == []
    assert await crud.get_thread_detail(db, thread.id) is None


@pytest.mark.asyncio
async def test_upsert_subscription_requires_owner(db):
    with pytest.raises(ValueError):
        await crud.upsert_subscription(
            db,
            None,
            plan=models.PlanType.pro,
            stripe_customer_id="cus_unknown",
            stripe_subscription_id="sub_unknown",
            status=models.SubscriptionStatus.active,
        )


@pytest.mark.asyncio
async def test_preferences_default_and_upsert(db):
    user = await crud.get_or_create_user(db, "Test Agent", "agent@example.com")
    pref = await crud.upsert_preferences(
        db, user.id, tone_profile={"style": "friendly"}, auto_features={"digest": True}
    )
    assert pref.tone_profile == {"style": "friendly"}
    pref2 = await crud.upsert_preferences(db, user.id, rules="no price promises")
    fetched = await crud.get_preferences(db, user.id)
    assert fetched.id == pref.id
    assert fetched.auto_features == {"digest": True}
    assert pref2.rules == "no price promises"