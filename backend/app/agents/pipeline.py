from app.agents import (
    action_extractor,
    auto_pilot,
    categorizer,
    lead_hints,
    prioritizer,
    reader,
    reply_drafter,
    sentiment,
)
from app.agents.base import with_llm
from app.db import crud, models
from app.services import gmail_sync


def _clamp_score(value) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _clean_actions(raw: list | None) -> list[dict]:
    allowed = set(action_extractor.ACTION_TYPES)
    cleaned = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in allowed:
            continue
        cleaned.append(
            {
                "type": item["type"],
                "description": str(item.get("description", ""))[:2000],
                "due": item.get("due") or None,
                "contact": item.get("contact") or None,
                "property": item.get("property") or None,
            }
        )
    return cleaned


async def process_email(db, email_id, llm=None) -> dict:
    """Run the full agent pipeline on one email and persist its outputs.

    Returns a dict of every agent's raw result for tests and debugging.
    """
    llm = with_llm(llm)
    email = await db.get(models.Email, email_id)
    if email is None:
        raise ValueError("Email not found")
    thread = await db.get(models.Thread, email.thread_id)

    thread_emails = await crud.list_emails_for_thread(db, thread.id)
    thread_emails.sort(key=lambda m: m.received_at)

    email_dict = {
        "from_addr": email.from_addr,
        "to_addr": email.to_addr,
        "subject": email.subject,
        "body": email.body,
        "received_at": email.received_at.isoformat() if email.received_at else "",
        "thread_id": str(thread.thread_id),
        "has_attachment": email.has_attachment,
    }

    read = reader.read_email(email_dict, llm=llm)
    clean = dict(email_dict)
    if read.get("body_clean"):
        clean["body"] = read["body_clean"]

    cat = categorizer.classify_email(clean, llm=llm)
    category_name = (
        cat.get("category")
        if cat.get("category") in categorizer.CATEGORIES
        else None
    )

    sent = sentiment.analyze_sentiment(clean, llm=llm)
    sentiment_value = {
        "mood": sent.get("mood", "neutral"),
        "intensity": float(sent.get("intensity", 0.0) or 0),
        "warning": bool(sent.get("warning", False)),
    }

    prio = prioritizer.score_email(
        clean, category_name or "unknown", sentiment=sentiment_value, llm=llm
    )

    is_noise = category_name in ("spam", "newsletter")

    actions_raw = None
    if not is_noise:
        actions_raw = action_extractor.extract_actions(clean, category_name or "unknown", llm=llm)

    thread.category = (
        models.CategoryType(category_name) if category_name else thread.category
    )
    thread.priority_score = _clamp_score(prio.get("score"))
    thread.flags = prio.get("flags") or []
    thread.pipeline_hints = lead_hints.derive_hints(category_name, thread.flags)
    if read.get("summary"):
        thread.summary = read["summary"]

    email.ai_summary = read.get("summary") or email.ai_summary
    email.sentiment = sentiment_value

    prefs = await crud.get_preferences(db, thread.user_id)
    auto_features = prefs.auto_features if prefs else {}

    drafts = []
    auto_decision = None
    if not is_noise:
        tone_profile = prefs.tone_profile if prefs else None
        rules = prefs.rules if prefs else None
        thread_dicts = [
            {
                "from_addr": m.from_addr,
                "received_at": m.received_at.isoformat() if m.received_at else "",
                "subject": m.subject,
                "body": m.body,
            }
            for m in thread_emails
        ]
        reply = reply_drafter.draft_reply(
            thread_dicts, tone_profile=tone_profile, rules=rules, llm=llm
        )
        if reply.get("reply_text"):
            auto_decision = auto_pilot.decide(
                email=clean,
                category=category_name,
                sentiment=sentiment_value,
                priority_score=thread.priority_score,
                draft_text=reply["reply_text"],
                preferences=auto_features,
                llm=llm,
            )
            draft = await crud.add_draft(
                db,
                email.id,
                reply["reply_text"],
                tone=reply.get("suggested_tone", ""),
                auto_decision=auto_decision,
            )
            drafts.append(draft.id)
            if auto_decision and auto_decision.get("send"):
                await _maybe_autosend(db, draft, auto_decision)
    else:
        reply = {}

    actions = []
    for a in _clean_actions((actions_raw or {}).get("actions")):
        item = await crud.add_action_item(
            db,
            email.id,
            models.ActionType(a["type"]),
            a["description"],
            due=a["due"],
            contact=a["contact"],
            property=a["property"],
        )
        actions.append(str(item.id))

    if not is_noise:
        await _maybe_notify(db, thread, email, sentiment_value)

    await db.flush()
    return {
        "email_id": str(email.id),
        "reader": read,
        "category": category_name,
        "sentiment": sentiment_value,
        "priority": prio,
        "reply": reply,
        "auto_decision": auto_decision,
        "drafts_created": len(drafts),
        "actions_created": len(actions),
    }


async def _maybe_autosend(db, draft, auto_decision: dict) -> None:
    """Send an auto-pilot-approved draft, but only if the account granted send."""
    # Resolve the account through the email -> thread -> user chain.
    email = await db.get(models.Email, draft.email_id)
    thread = await db.get(models.Thread, email.thread_id) if email else None
    account = None
    if thread is not None:
        account = await crud.get_email_account(db, thread.user_id, models.ProviderType.gmail)

    if not gmail_sync.account_can_send(account):
        auto_decision["sent"] = False
        auto_decision["send_error"] = "send scope not granted"
        draft.auto_decision = dict(auto_decision)
        return

    try:
        result = await gmail_sync.send_draft_reply(db, draft.id)
        auto_decision["sent"] = True
        auto_decision["sent_message_id"] = result.get("sent_message_id")
    except Exception as e:  # never let a send failure break processing
        auto_decision["sent"] = False
        auto_decision["send_error"] = str(e)
    draft.auto_decision = dict(auto_decision)


async def _maybe_notify(db, thread, email, sentiment_value: dict) -> None:
    """Create a notification when a thread needs the agent's attention now."""
    flags = set(thread.flags or [])
    score = thread.priority_score
    note_type = None
    if "hot_lead" in flags:
        note_type = models.NotificationType.hot_lead
    elif "closing_deadline" in flags:
        note_type = models.NotificationType.closing
    elif "complaint" in flags or sentiment_value.get("warning"):
        note_type = models.NotificationType.complaint
    elif score is not None and score >= 85:
        note_type = models.NotificationType.urgent

    if note_type is None:
        return

    await crud.add_notification(
        db,
        thread.user_id,
        note_type,
        title=thread.subject or "Email needs attention",
        body=email.ai_summary or thread.summary,
        thread_id=thread.id,
        email_id=email.id,
    )