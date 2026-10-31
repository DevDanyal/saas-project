from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents import (
    action_extractor,
    auto_pilot,
    categorizer,
    digest,
    lead_hints,
    pipeline,
    prioritizer,
    reader,
    reply_drafter,
    sentiment,
)
from app.db import crud, models
from app.db.base import Base
from app.services.llm import FakeLlm

EMAIL = {
    "from_addr": "buyer@example.com",
    "to_addr": "agent@example.com",
    "subject": "Looking near the lake",
    "body": "Hi, we are pre-approved for $450k and ready to buy a lakefront home asap.",
    "received_at": "2026-09-20T09:00:00+00:00",
    "thread_id": "thread-1",
    "has_attachment": False,
}

read_resp = {
    "from": "buyer@example.com",
    "to": "agent@example.com",
    "subject": "Looking near the lake",
    "received_at": "2026-09-20T09:00:00+00:00",
    "body_clean": "We are pre-approved for $450k and ready to buy.",
    "thread_id": "thread-1",
    "has_attachment": False,
    "reply_depth": 0,
    "summary": "Pre-approved buyer wants to see lakefront homes soon.",
}
sentiment_resp = {"mood": "positive", "intensity": 0.8, "warning": False}
priority_resp = {"score": 92, "urgency": "high", "flags": ["hot_lead", "pre_approved"]}
actions_resp = {
    "actions": [
        {"type": "call", "description": "Call re: showings", "due": "", "contact": "buyer@example.com", "property": "lakefront"}
    ]
}
reply_resp = {
    "reply_text": "Congrats on the pre-approval! Let's find your lakefront home.",
    "suggested_tone": "friendly",
}
auto_pilot_resp = {"send": True, "confidence": 0.97, "reason": "Low-risk vendor reply."}


def build_fake():
    return FakeLlm(
        by_keyword={
            "Normalize this raw email": read_resp,
            "Classify this email thread": {"category": "lead"},
            "assess the writer's sentiment": sentiment_resp,
            "Scoring order": priority_resp,
            "Extract every action": actions_resp,
            "Draft a reply": reply_resp,
            "safe to send automatically": auto_pilot_resp,
        }
    )


def test_categorizer():
    out = categorizer.classify_email(EMAIL, llm=FakeLlm(by_keyword={"pre-approved": {"category": "lead"}}))
    assert out["category"] == "lead"


def test_sentiment():
    out = sentiment.analyze_sentiment(EMAIL, llm=FakeLlm(by_keyword={"positive": sentiment_resp}))
    assert out["mood"] == "positive"
    assert out["warning"] is False


def test_prioritizer():
    out = prioritizer.score_email(EMAIL, "lead", {"mood": "positive"}, llm=FakeLlm(by_keyword={"Scoring order": priority_resp}))
    assert out["score"] == 92
    assert "pre_approved" in out["flags"]


def test_reply_drafter():
    out = reply_drafter.draft_reply([EMAIL], tone_profile={"style": "friendly"}, llm=FakeLlm(by_keyword={"Draft a reply": reply_resp}))
    assert "pre-approval" in out["reply_text"]


def test_action_extractor():
    out = action_extractor.extract_actions(EMAIL, "lead", llm=FakeLlm(by_keyword={"Extract every action": actions_resp}))
    assert out["actions"][0]["type"] == "call"


def test_reader():
    out = reader.read_email(EMAIL, llm=FakeLlm(by_keyword={"Normalize this raw email": read_resp}))
    assert out["reply_depth"] == 0
    assert "body_clean" in out


def test_digest_builds_brief():
    digest_resp = {
        "brief": "Three hot leads and one closing deadline needs attention today.",
        "sections": {"hot_leads": ["Smith wants lakefront"], "closings": [], "follow_ups": [], "other": []},
    }
    fake = FakeLlm(by_keyword={"morning brief": digest_resp})
    out = digest.build_digest(
        [{"subject": "Lakefront buyer", "priority_score": 92, "category": "lead", "summary": "pre-approved"}],
        [{"type": "call", "description": "Call re closing", "due": "2026-09-22", "contact": "x"}],
        llm=fake,
    )
    assert "hot leads" in out["brief"]
    assert out["sections"]["hot_leads"][0] == "Smith wants lakefront"


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
async def test_pipeline_persists_all_outputs(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    await crud.upsert_preferences(db, user.id, tone_profile={"style": "friendly"})
    thread = await crud.upsert_thread(db, user.id, "ext-thread-1", "Looking near the lake")
    email = await crud.insert_email(
        db, thread.id, "msg-1", EMAIL["from_addr"], EMAIL["to_addr"],
        EMAIL["subject"], EMAIL["body"], datetime.now(timezone.utc),
    )

    result = await pipeline.process_email(db, email.id, llm=build_fake())

    assert result["category"] == "lead"
    assert result["priority"]["score"] == 92
    assert result["drafts_created"] == 1
    assert result["actions_created"] == 1

    await db.refresh(thread)
    await db.refresh(email)

    assert thread.category == models.CategoryType.lead
    assert thread.priority_score == 92
    assert set(thread.flags) == {"hot_lead", "pre_approved"}
    assert thread.summary == read_resp["summary"]

    assert email.sentiment == sentiment_resp
    assert email.ai_summary == read_resp["summary"]

    drafts = await db.execute(select(models.AiDraft).where(models.AiDraft.email_id == email.id))
    draft = drafts.scalar_one()
    assert draft.status == models.DraftStatus.draft

    items = await db.execute(
        select(models.ActionItem).where(models.ActionItem.email_id == email.id)
    )
    item = items.scalar_one()
    assert item.type == models.ActionType.call

    # scores are clamped to 0-100
    assert pipeline._clamp_score(250) == 100
    assert pipeline._clamp_score(-5) == 0


@pytest.mark.asyncio
async def test_pipeline_skips_drafts_for_spam(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-2", "Winner!")
    email = await crud.insert_email(
        db, thread.id, "msg-2", "spam@example.com", "agent@example.com",
        "Winner!", "You have won a prize!", datetime.now(timezone.utc),
    )
    fake = build_fake()
    fake._by_keyword["Classify this email thread"] = {"category": "spam"}

    result = await pipeline.process_email(db, email.id, llm=fake)

    assert result["category"] == "spam"
    assert result["drafts_created"] == 0
    assert result["actions_created"] == 0


def test_autopilot_sends_low_risk_when_enabled():
    fake = FakeLlm(by_keyword={"safe to send automatically": auto_pilot_resp})
    out = auto_pilot.decide(
        email={"body_clean": "Are you free Tuesday?"},
        category="vendor",
        sentiment={"mood": "neutral", "intensity": 0.1, "warning": False},
        priority_score=10,
        draft_text="Thanks, see you Tuesday.",
        preferences={"autopilot": True, "autopilot_confidence": 0.9},
        llm=fake,
    )
    assert out["send"] is True
    assert out["blockers"] == []


def test_autopilot_guardrails_block_risky_cases():
    fake = FakeLlm(by_keyword={"safe to send automatically": auto_pilot_resp})
    base = dict(
        email={"body_clean": "hi"},
        category="vendor",
        sentiment={"mood": "neutral", "intensity": 0.1, "warning": False},
        priority_score=10,
        draft_text="Thanks, see you Tuesday.",
        preferences={"autopilot": True, "autopilot_confidence": 0.9},
        llm=fake,
    )

    assert auto_pilot.decide(**{**base, "priority_score": 90})["send"] is False
    assert auto_pilot.decide(
        **{**base, "sentiment": {"mood": "neutral", "intensity": 0.1, "warning": True}}
    )["send"] is False
    assert auto_pilot.decide(**{**base, "draft_text": "Your offer is $450,000."})["send"] is False
    assert auto_pilot.decide(**{**base, "category": "legal"})["send"] is False
    assert auto_pilot.decide(**{**base, "preferences": {}})["send"] is False


def test_lead_hints_mapping():
    hints = lead_hints.derive_hints("lead", ["hot_lead", "pre_approved", "hot_lead"])
    assert hints == ["Hot lead", "Buyer pre-approved"]
    assert lead_hints.pipeline_side("lead", ["ready_to_list"]) == "seller"
    assert lead_hints.pipeline_side("lead", ["hot_lead"]) == "buyer"


@pytest.mark.asyncio
async def test_pipeline_records_hints_and_autopilot(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-3", "Looking near the lake")
    email = await crud.insert_email(
        db, thread.id, "msg-3", "buyer@example.com", "agent@example.com",
        "Looking near the lake", "pre-approved $450k", datetime.now(timezone.utc),
    )
    result = await pipeline.process_email(db, email.id, llm=build_fake())

    assert "Hot lead" in (thread.pipeline_hints or [])
    assert result["auto_decision"] is not None
    assert result["auto_decision"]["send"] is False

    drafts = await db.execute(
        select(models.AiDraft).where(models.AiDraft.email_id == email.id)
    )
    assert drafts.scalar_one().auto_decision is not None

    notes = await db.execute(
        select(models.Notification).where(models.Notification.user_id == user.id)
    )
    assert notes.scalar_one().type == models.NotificationType.hot_lead