from datetime import datetime, timezone
import math

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
    except (TypeError, ValueError, OverflowError):
        return None


def _fallback_summary(text: str) -> str:
    """Deterministic one-liner so every processed email has a scannable summary."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    sentence = cleaned.split(". ")[0].strip()
    if len(sentence) > 160:
        sentence = sentence[:157].rstrip() + "…"
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


def _parse_due(value) -> datetime | None:
    """Coerce a model-supplied date string into a datetime for the DB column."""
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for parser in (
        lambda t: datetime.fromisoformat(t),
        lambda t: datetime.strptime(t, "%m/%d/%Y"),
        lambda t: datetime.strptime(t, "%Y/%m/%d"),
        lambda t: datetime.strptime(t, "%B %d, %Y"),
        lambda t: datetime.strptime(t, "%b %d, %Y"),
    ):
        try:
            parsed = parser(text)
            break
        except ValueError:
            continue
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _safe_intensity(value) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return max(0.0, min(1.0, number))


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
                "description": str(item.get("description") or "")[:2000],
                "due": _parse_due(item.get("due")),
                "contact": (str(item["contact"])[:255] if item.get("contact") else None),
                "property": (str(item["property"])[:255] if item.get("property") else None),
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

    # A single provider outage must not wipe out an email's grouping. Track
    # whether the LLM is reachable and fall back to deterministic logic.
    llm_down = False
    try:
        read = reader.read_email(email_dict, llm=llm)
    except Exception:
        read = {}
        llm_down = True
    clean = dict(email_dict)
    if read.get("body_clean"):
        clean["body"] = read["body_clean"]
    summary_value = (read.get("summary") or "").strip() or _fallback_summary(
        clean.get("body", "")
    )
    if not summary_value:
        summary_value = _fallback_summary(clean.get("subject", ""))

    category_name = None
    if not llm_down:
        try:
            cat = categorizer.classify_email(clean, llm=llm)
            category_name = categorizer.normalize_category(cat.get("category"))
        except Exception:
            llm_down = True
    if category_name is None:
        category_name = categorizer.fallback_category(clean)

    sentiment_value = {"mood": "neutral", "intensity": 0.0, "warning": False}
    if not llm_down:
        try:
            sent = sentiment.analyze_sentiment(clean, llm=llm)
            sentiment_value = {
                "mood": str(sent.get("mood", "neutral"))[:32],
                "intensity": _safe_intensity(sent.get("intensity")),
                "warning": bool(sent.get("warning", False)),
            }
        except Exception:
            pass

    prio: dict = {}
    if not llm_down:
        try:
            prio = prioritizer.score_email(
                clean, category_name or "unknown", sentiment=sentiment_value, llm=llm
            )
        except Exception:
            prio = {}

    is_noise = category_name in ("spam", "newsletter")

    actions_raw = None
    if not is_noise and not llm_down:
        try:
            actions_raw = action_extractor.extract_actions(
                clean, category_name or "unknown", llm=llm
            )
        except Exception:
            actions_raw = None

    allowed_flags = set(prioritizer.FLAGS)
    clean_flags = [f for f in (prio.get("flags") or []) if f in allowed_flags]
    thread.category = (
        models.CategoryType(category_name) if category_name else thread.category
    )
    thread.priority_score = _clamp_score(prio.get("score"))
    thread.flags = clean_flags
    thread.pipeline_hints = lead_hints.derive_hints(category_name, clean_flags)
    if summary_value:
        thread.summary = summary_value

    email.ai_summary = summary_value or email.ai_summary
    email.sentiment = sentiment_value

    prefs = await crud.get_preferences(db, thread.user_id)
    auto_features = prefs.auto_features if prefs else {}

    drafts = []
    auto_decision = None
    if not is_noise and not llm_down:
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
        try:
            reply = reply_drafter.draft_reply(
                thread_dicts, tone_profile=tone_profile, rules=rules, llm=llm
            )
        except Exception:
            reply = {}
        if reply.get("reply_text"):
            existing_draft = await crud.get_draft_for_email(db, email.id)
            is_new = existing_draft is None
            needs_decision = is_new or existing_draft.status == models.DraftStatus.draft
            draft_text = str(reply.get("reply_text")).strip()
            draft_tone = str(reply.get("suggested_tone") or "")[:64]
            if needs_decision:
                try:
                    auto_decision = auto_pilot.decide(
                        email=clean,
                        category=category_name,
                        sentiment=sentiment_value,
                        priority_score=thread.priority_score,
                        draft_text=draft_text,
                        preferences=auto_features,
                        llm=llm,
                    )
                except Exception:
                    auto_decision = None

            if is_new:
                draft = await crud.add_draft(
                    db,
                    email.id,
                    draft_text,
                    tone=draft_tone,
                    auto_decision=auto_decision,
                )
                drafts.append(draft.id)
                if auto_decision and auto_decision.get("send"):
                    await _maybe_autosend(db, draft, auto_decision)
            else:
                # Re-processing must not create duplicates. Refresh an
                # unsent draft in place and leave sent drafts untouched.
                if existing_draft.status == models.DraftStatus.draft:
                    existing_draft.text = draft_text
                    existing_draft.tone = draft_tone
                    existing_draft.auto_decision = auto_decision
                    await db.flush()
    else:
        reply = {}

    existing_actions = await crud.list_action_items_for_email(db, email.id)
    seen_actions = {
        (a.type.value, (a.description or "").strip()) for a in existing_actions
    }
    actions = []
    for a in _clean_actions((actions_raw or {}).get("actions")):
        key = (a["type"], a["description"].strip())
        if key in seen_actions:
            continue
        seen_actions.add(key)
        try:
            async with db.begin_nested():
                item = await crud.add_action_item(
                    db,
                    email.id,
                    models.ActionType(a["type"]),
                    a["description"],
                    due=a["due"],
                    contact=a["contact"],
                    property=a["property"],
                )
        except Exception:
            # A malformed action must not roll back the whole email.
            continue
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

    if await crud.notification_exists(db, email.id, note_type):
        return

    await crud.add_notification(
        db,
        thread.user_id,
        note_type,
        title=(thread.subject or "Email needs attention")[:255],
        body=email.ai_summary or thread.summary,
        thread_id=thread.id,
        email_id=email.id,
    )