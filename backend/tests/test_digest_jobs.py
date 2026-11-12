from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import crud, models
from app.db.base import Base
from app.services import digest_service, inbox_jobs


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        now = datetime.now(timezone.utc)
        user = await crud.create_user(db, "Agent", "agent@example.com")
        thread = await crud.upsert_thread(
            db,
            user.id,
            "ext-1",
            "Lakefront buyer",
            last_activity_at=now,
            category=models.CategoryType.lead,
            priority_score=92,
            summary="Pre-approved buyer.",
        )
        email = await crud.insert_email(
            db,
            thread.id,
            "msg-1",
            "buyer@example.com",
            "agent@example.com",
            "Lakefront buyer",
            "We are pre-approved for $450k.",
            now,
        )
        await crud.add_action_item(
            db,
            email.id,
            models.ActionType.call,
            "Call re: showings",
            due=now,
            contact="buyer@example.com",
        )
        await db.commit()

    yield factory, user, thread, email
    await engine.dispose()


def _fake_llm(calls: list):
    def llm(system: str, user: str) -> dict:
        calls.append(user)
        return {
            "brief": "One hot lead today.",
            "sections": {
                "hot_leads": ["Lakefront buyer"],
                "closings": [],
                "follow_ups": [],
                "other": [],
            },
        }

    return llm


@pytest.mark.asyncio
async def test_digest_is_cached_per_day(ctx):
    factory, user, _, _ = ctx
    calls: list = []

    async with factory() as db:
        first = await digest_service.get_or_build_digest(
            db, user.id, llm=_fake_llm(calls)
        )
        await db.commit()
        second = await digest_service.get_or_build_digest(
            db, user.id, llm=_fake_llm(calls)
        )

    assert first["brief"] == "One hot lead today."
    assert first["threads_in_window"] == 1
    assert first["actions_in_window"] == 1
    assert second["generated_at"] == first["generated_at"]
    assert len(calls) == 1

    async with factory() as db:
        refreshed = await digest_service.get_or_build_digest(
            db, user.id, refresh=True, llm=_fake_llm(calls)
        )
        await db.commit()

    assert refreshed["brief"] == "One hot lead today."
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_sync_and_process_user_runs_pipeline(ctx, monkeypatch):
    factory, user, _, _ = ctx
    processed: list = []

    async def fake_sync(db, user_id, service=None, max_results=20):
        return {"threads": 1, "emails_added": 0, "emails_skipped": 0, "errors": 0}

    async def fake_process(db, email_id, llm=None):
        processed.append(email_id)
        return {"email_id": str(email_id)}

    monkeypatch.setattr(inbox_jobs.gmail_sync, "sync_user_inbox", fake_sync)
    monkeypatch.setattr(inbox_jobs.pipeline, "process_email", fake_process)

    async with factory() as db:
        stats = await inbox_jobs.sync_and_process_user(db, user.id)

    assert stats["sync"]["threads"] == 1
    assert stats["emails_processed"] == 1
    assert len(processed) == 1


@pytest.mark.asyncio
async def test_sync_failure_is_reported(ctx, monkeypatch):
    factory, user, _, _ = ctx

    async def boom(db, user_id, service=None, max_results=20):
        raise ValueError("No Gmail account connected")

    monkeypatch.setattr(inbox_jobs.gmail_sync, "sync_user_inbox", boom)

    async with factory() as db:
        stats = await inbox_jobs.sync_and_process_user(db, user.id)

    assert "No Gmail account connected" in stats["sync_error"]
    assert stats["emails_processed"] == 0
