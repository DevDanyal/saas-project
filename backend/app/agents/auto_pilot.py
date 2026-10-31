"""Auto-Pilot agent: decides whether a draft reply may be sent without review.

Safety is enforced in two layers:
1. Deterministic guardrails here (never trust the LLM alone for sending).
2. The LLM's own send/confidence judgement.

The final decision requires BOTH layers to agree. Nothing is ever sent
silently: an approved draft is marked for send and still recorded for audit.
"""

import re

from app.agents.base import base_system, with_llm

TRUSTED_CATEGORIES = {"vendor", "internal"}
BLOCKED_CATEGORIES = {"legal", "financial", "spam", "lead", "client"}

RISKY_PATTERNS = [
    r"\$\s?\d",
    r"\bapr\b",
    r"\binterest rate\b",
    r"\bpre-?approved\b",
    r"\bmortgage\b",
    r"\bguarantee\b",
    r"\bpromise\b",
    r"\bwire\b",
    r"\bearnest\b",
    r"\bdeposit\b",
    r"\bsign\b",
    r"\bcontract\b",
    r"\blegal\b",
    r"\bclosing date\b",
]

DEFAULT_CONFIDENCE_CUTOFF = 0.9


def _clamp(value, low=0.0, high=1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return 0.0


def guardrail_blocks(
    category: str | None,
    sentiment: dict | None,
    priority_score: int | None,
    draft_text: str,
) -> list[str]:
    """Deterministic reasons the auto-pilot must NOT send. Empty = clear."""
    blockers: list[str] = []

    if category in BLOCKED_CATEGORIES:
        blockers.append(f"category '{category}' is never auto-sent")
    if category not in TRUSTED_CATEGORIES:
        blockers.append("category is not on the trusted list")

    sent = sentiment or {}
    if sent.get("warning"):
        blockers.append("sentiment warning flag is set")
    if sent.get("mood") in ("negative", "urgent"):
        blockers.append(f"negative/urgent mood ({sent.get('mood')})")
    if _clamp(sent.get("intensity", 0)) >= 0.7:
        blockers.append("sentiment intensity is high")

    if priority_score is not None and priority_score >= 70:
        blockers.append(f"priority score {priority_score} is too high for auto-send")

    text = (draft_text or "").lower()
    for pattern in RISKY_PATTERNS:
        if re.search(pattern, text):
            blockers.append(f"draft contains risky term: {pattern}")
            break

    return blockers


def decide(
    email: dict,
    category: str | None,
    sentiment: dict | None,
    priority_score: int | None,
    draft_text: str,
    preferences: dict | None = None,
    llm=None,
) -> dict:
    """Return {"send", "confidence", "reason", "blockers"} for a draft.

    preferences: agent_preferences.auto_features dict, e.g.
        {"autopilot": True, "autopilot_confidence": 0.9}
    """
    llm = with_llm(llm)
    prefs = preferences or {}
    enabled = bool(prefs.get("autopilot", False))
    cutoff = _clamp(prefs.get("autopilot_confidence", DEFAULT_CONFIDENCE_CUTOFF))

    user = (
        "Decide whether this reply is safe to send automatically with no human review.\n"
        "Be conservative: if there is ANY doubt, do not send.\n"
        f"Category: {category}\n"
        f"Sentiment: {sentiment}\n"
        f"Priority score: {priority_score}\n"
        f"Draft reply:\n{draft_text[:2000]}\n"
        "\nReturn JSON: {\"send\": false, \"confidence\": 0.0, \"reason\": \"...\"}"
    )
    raw = llm(base_system("You are the Auto-Pilot agent."), user)

    llm_send = bool(raw.get("send", False))
    confidence = _clamp(raw.get("confidence", 0.0))
    blockers = guardrail_blocks(category, sentiment, priority_score, draft_text)

    send = enabled and llm_send and confidence >= cutoff and not blockers
    reason = str(raw.get("reason", "")).strip()
    if blockers:
        reason = (reason + " | blocked: " + "; ".join(blockers)).strip(" |")
    elif not enabled:
        reason = (reason + " | autopilot disabled in preferences").strip(" |")

    return {
        "send": send,
        "confidence": confidence,
        "reason": reason,
        "blockers": blockers,
    }