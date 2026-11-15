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


def build_fake(category: str = "lead"):
    return FakeLlm(
        by_keyword={
            "Normalize this raw email": read_resp,
            "Classify this email thread": {"category": category},
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


def test_categorizer_normalizes_model_variants():
    assert categorizer.normalize_category("Lead") == "lead"
    assert categorizer.normalize_category("Customers") == "client"
    assert categorizer.normalize_category("FINANCE") == "financial"
    assert categorizer.normalize_category("sellers") == "client"
    assert categorizer.normalize_category("not-a-category") is None


def test_categorizer_fallback_keywords():
    assert categorizer.fallback_category({"subject": "You won a prize"}) == "spam"
    assert categorizer.fallback_category({"subject": "Monthly market report", "body": "unsubscribe"}) == "newsletter"
    assert categorizer.fallback_category({"body": "Our mortgage pre-approval is ready"}) == "financial"
    assert categorizer.fallback_category({"body": "Can we schedule a showing?"}) == "lead"
    assert categorizer.fallback_category({"body": "random chatter"}) == "lead"
    assert (
        categorizer.fallback_category(
            {"body": "hi danyal i want a professional webbsite for my bisuness"}
        )
        == "client"
    )


def test_sender_is_external():
    assert categorizer.sender_is_external(
        "Aidevdanyal <aidevdanyal@gmail.com>", "devdanyal9@gmail.com"
    )
    assert not categorizer.sender_is_external(
        "colleague@brokerage.com", "agent@brokerage.com"
    )
    assert not categorizer.sender_is_external(
        "agent@gmail.com", "agent@gmail.com"
    )


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
async def test_pipeline_moves_external_internal_mail_to_customers(db):
    user = await crud.get_or_create_user(db, "Agent", "devdanyal9@gmail.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-web", "website")
    email = await crud.insert_email(
        db, thread.id, "msg-web",
        "Aidevdanyal <aidevdanyal@gmail.com>", "devdanyal9@gmail.com",
        "website for my bisuness",
        "hi danyal i want a professional webbsite for my bisuness can u make for me ?",
        datetime.now(timezone.utc),
    )

    fake = build_fake(category="internal")
    fake._by_keyword["Normalize this raw email"] = {
        **read_resp,
        "subject": "website for my bisuness",
        "body_clean": "hi danyal i want a professional webbsite for my bisuness can u make for me ?",
    }

    result = await pipeline.process_email(db, email.id, llm=fake)
    assert result["category"] == "client"
    await db.refresh(thread)
    assert thread.category == models.CategoryType.client


@pytest.mark.asyncio
async def test_pipeline_keeps_same_domain_team_mail_internal(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@brokerage.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-team", "Team")
    email = await crud.insert_email(
        db, thread.id, "msg-team", "colleague@brokerage.com", "agent@brokerage.com",
        "Team meeting", "Team meeting moved to 10am.", datetime.now(timezone.utc),
    )

    result = await pipeline.process_email(
        db, email.id, llm=build_fake(category="internal")
    )

    assert result["category"] == "internal"
    await db.refresh(thread)
    assert thread.category == models.CategoryType.internal


@pytest.mark.asyncio
async def test_pipeline_stores_action_due_as_datetime(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-due", "Closing")
    email = await crud.insert_email(
        db, thread.id, "msg-due", EMAIL["from_addr"], EMAIL["to_addr"],
        EMAIL["subject"], EMAIL["body"], datetime.now(timezone.utc),
    )
    fake = build_fake()
    fake._by_keyword["Extract every action"] = {
        "actions": [
            {
                "type": "calendar",
                "description": "Schedule closing walkthrough",
                "due": "2026-10-01",
                "contact": "buyer@example.com",
                "property": "12 Lake Rd",
            }
        ]
    }

    await pipeline.process_email(db, email.id, llm=fake)

    item = (await db.execute(
        select(models.ActionItem).where(models.ActionItem.email_id == email.id)
    )).scalar_one()
    assert isinstance(item.due, datetime)
    assert item.due.date().isoformat() == "2026-10-01"


@pytest.mark.asyncio
async def test_pipeline_reprocessing_is_idempotent(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-idem", "Looking near the lake")
    email = await crud.insert_email(
        db, thread.id, "msg-idem", EMAIL["from_addr"], EMAIL["to_addr"],
        EMAIL["subject"], EMAIL["body"], datetime.now(timezone.utc),
    )

    first = await pipeline.process_email(db, email.id, llm=build_fake())
    second = await pipeline.process_email(db, email.id, llm=build_fake())

    assert first["drafts_created"] == 1
    assert first["actions_created"] == 1
    assert second["drafts_created"] == 0
    assert second["actions_created"] == 0

    drafts = (await db.execute(
        select(models.AiDraft).where(models.AiDraft.email_id == email.id)
    )).scalars().all()
    items = (await db.execute(
        select(models.ActionItem).where(models.ActionItem.email_id == email.id)
    )).scalars().all()
    notes = (await db.execute(
        select(models.Notification).where(models.Notification.email_id == email.id)
    )).scalars().all()
    assert len(drafts) == 1
    assert len(items) == 1
    assert len(notes) == 1


@pytest.mark.asyncio
async def test_pipeline_drops_unknown_flags(db):
    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-flags", "Flags")
    email = await crud.insert_email(
        db, thread.id, "msg-flags", EMAIL["from_addr"], EMAIL["to_addr"],
        EMAIL["subject"], EMAIL["body"], datetime.now(timezone.utc),
    )
    fake = build_fake()
    fake._by_keyword["Scoring order"] = {
        "score": 50,
        "urgency": "low",
        "flags": ["hot_lead", "totally_made_up"],
    }

    await pipeline.process_email(db, email.id, llm=fake)

    await db.refresh(thread)
    assert thread.flags == ["hot_lead"]


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


@pytest.mark.asyncio
async def test_pipeline_survives_llm_outage(db):
    """A provider outage must still group the email and persist a summary."""
    def boom(system, user, temperature=0.2, max_tokens=2048):
        raise RuntimeError("provider down")

    user = await crud.get_or_create_user(db, "Agent", "agent@example.com")
    thread = await crud.upsert_thread(db, user.id, "ext-thread-outage", "Mortgage pre-approval")
    email = await crud.insert_email(
        db, thread.id, "msg-outage", "loan@example.com", "agent@example.com",
        "Mortgage pre-approval", "Your loan is pre-approved, closing soon.",
        datetime.now(timezone.utc),
    )

    result = await pipeline.process_email(db, email.id, llm=boom)

    assert result["category"] == "financial"
    await db.refresh(thread)
    await db.refresh(email)
    assert thread.category == models.CategoryType.financial
    assert email.ai_summary


def test_parse_due_handles_model_strings():
    from datetime import datetime, timezone

    assert pipeline._parse_due("") is None
    assert pipeline._parse_due(None) is None
    assert pipeline._parse_due("not a date") is None
    assert pipeline._parse_due("2026-09-22") == datetime(2026, 9, 22, tzinfo=timezone.utc)
    assert pipeline._parse_due("2026-09-22T15:30:00Z") == datetime(
        2026, 9, 22, 15, 30, tzinfo=timezone.utc
    )
    assert pipeline._parse_due("09/22/2026") == datetime(2026, 9, 22, tzinfo=timezone.utc)
    assert pipeline._parse_due("September 22, 2026") == datetime(
        2026, 9, 22, tzinfo=timezone.utc
    )


def test_clean_actions_coerces_and_drops_bad_items():
    cleaned = pipeline._clean_actions(
        [
            {
                "type": "call",
                "description": None,
                "due": "banana",
                "contact": 123,
                "property": {"x": 1},
            },
            {"type": "bogus", "description": "ignore me"},
            "not-an-object",
            None,
        ]
    )
    assert len(cleaned) == 1
    action = cleaned[0]
    assert action["type"] == "call"
    assert action["description"] == ""
    assert action["due"] is None
    assert action["contact"] == "123"
    assert action["property"] == "{'x': 1}"


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