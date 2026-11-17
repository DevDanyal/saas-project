from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone


def _iso(dt):
    return dt.isoformat() if dt else None


def _days_since(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _snippets(text: str, limit: int = 2):
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+', " ".join(text.split()))
    out = []
    for p in parts:
        p = p.strip()
        if len(p) < 20:
            continue
        out.append(p[:180] + ("…" if len(p) > 180 else ""))
        if len(out) >= limit:
            break
    if not out and text.strip():
        out = [" ".join(text.split())[:180]]
    return out


def analyze_thread(thread, emails, actions, drafts) -> dict:
    texts = " \n".join((e.body or "") for e in emails)
    low = texts.lower()
    subj = (thread.subject or "").lower()
    flags = set(thread.flags or [])
    cat = thread.category.value if getattr(thread, "category", None) else "unknown"
    score = thread.priority_score or 0

    # --- Deal Risk Radar (pre-crime) ---
    last = max((e.received_at for e in emails if e.received_at), default=None)
    silence_days = _days_since(last)
    risk = 20
    reasons = []
    if silence_days is not None and silence_days >= 3:
        bump = min(30, silence_days * 5)
        risk += bump
        reasons.append(f"No reply/activity for {silence_days}d (stall risk)")
    if any(f in flags for f in ("complaint", "closing_deadline")):
        risk += 20
        reasons.append("High-stakes flag present (deadline/complaint)")
    if any((e.sentiment or {}).get("warning") or (e.sentiment or {}).get("mood") in ("angry", "anxious", "frustrated") for e in emails if e.sentiment):
        risk += 15
        reasons.append("Negative/at-risk sentiment detected")
    if "financ" in low or "pre-approv" in low or "lender" in low or "mortgage" in low:
        risk += 10
        reasons.append("Financing dependency in play")
    if score >= 80:
        risk += 10
        reasons.append("High priority thread")
    risk = max(5, min(99, risk))
    level = "critical" if risk >= 75 else "high" if risk >= 55 else "medium" if risk >= 35 else "low"

    next_actions = []
    if silence_days and silence_days >= 2:
        next_actions.append({"action": "Send a nudge/check-in", "why": "Silence increasing deal slip risk", "priority": "high"})
    if "inspect" in low:
        next_actions.append({"action": "Confirm inspection status & report", "why": "Inspection mentioned", "priority": "medium"})
    if "financ" in low or "lender" in low or "mortgage" in low:
        next_actions.append({"action": "Request lender/financing update", "why": "Financing dependency detected", "priority": "high"})
    if "apprais" in low:
        next_actions.append({"action": "Track appraisal outcome", "why": "Appraisal mentioned", "priority": "medium"})
    if "closing" in low or "title" in low:
        next_actions.append({"action": "Verify closing docs & title timeline", "why": "Closing/title signals found", "priority": "high"})
    open_actions = [a for a in actions if a.status.value == "open"]
    if open_actions and not next_actions:
        next_actions.append({"action": f"Complete: {open_actions[0].description[:80]}", "why": "Open action item pending", "priority": "medium"})
    if not next_actions:
        next_actions.append({"action": "Review and reply with clear next step", "why": "Keep momentum", "priority": "medium"})

    # --- War-Room (participants, leverage/intent, moves) ---
    parties = []
    for addr in {e.from_addr for e in emails if e.from_addr}:
        laddr = addr.lower()
        role = "contact"
        if any(k in laddr for k in ["lender", "mortgage", "bank"]): role = "lender"
        elif any(k in laddr for k in ["title", "escrow"]): role = "title/escrow"
        elif any(k in laddr for k in ["inspect"]): role = "inspector"
        elif any(k in laddr for k in ["attorney", "law", "legal"]): role = "attorney"
        elif any(k in laddr for k in ["agent", "realty", "broker"]): role = "agent"
        parties.append({"address": addr, "role": role})
    intents = []
    if "offer" in low or "price" in low: intents.append("price/offer negotiation")
    if "repair" in low or "credit" in low or "inspect" in low: intents.append("repairs/credits discussion")
    if "financ" in low or "pre-approv" in low: intents.append("financing validation")
    if "close" in low or "deadline" in low: intents.append("closing timeline pressure")
    if not intents: intents.append("general coordination")
    leverage = "high" if score >= 75 or "hot_lead" in flags else "medium" if score >= 40 else "low"
    moves = [
        {"move": "Anchor next step with a specific date/time ask", "predicted_effect": "Reduces ambiguity, speeds response"},
        {"move": "Bundle questions into one clear message", "predicted_effect": "Lowers back-and-forth, unblocks parties"},
    ]
    if risk >= 55:
        moves.insert(0, {"move": "Escalate with a concise risk-aware follow-up", "predicted_effect": "Surfaces blockers before slip"})

    # --- X-Ray Scanner (text/docs/promises/red flags) ---
    doc_terms = [k for k in ["contract", "disclosure", "inspection", "report", "addendum", "appraisal", "pre-approval", "proof of funds", "hoa", "title"] if k in low]
    money = re.findall(r"\$[\d,]+(?:\.\d{2})?", texts)[:5]
    dates = re.findall(r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?)\b", texts, re.I)[:5]
    promises = _snippets(texts, 2) if any(w in low for w in ["will", "promise", "confirm", "send", "schedule", "by "]) else []
    red_flags = []
    if "as is" in low: red_flags.append("‘As-is’ terms mentioned — verify risk/credits")
    if "delay" in low or "postpone" in low: red_flags.append("Delay language detected")
    if "cannot" in low or "can't" in low or "unable" in low: red_flags.append("Constraint/ inability stated")
    if not red_flags and risk >= 55: red_flags.append("Elevated deal risk signals — review thread closely")

    # --- Autonomous Deal Operator plan (approval-gated simulation) ---
    operator_plan = []
    for na in next_actions[:4]:
        operator_plan.append({
            "step": na["action"],
            "mode": "draft & queue (needs your approval)",
            "status": "ready",
            "guardrail": "High-stakes/legal/financial actions require explicit approval"
        })
    operator_plan.append({"step": "Monitor replies and auto-update deal status", "mode": "autonomous", "status": "armed", "guardrail": "Stops and escalates on risk/complaint"})

    # --- Provable Autopilot: evidence + audit ---
    evidence = []
    if thread.summary:
        src = emails[-1] if emails else None
        evidence.append({"claim": "Thread summary", "value": thread.summary, "source": src.from_addr if src else "thread", "quote": _snippets(src.body if src else texts, 1)})
    if flags:
        src = emails[-1] if emails else None
        evidence.append({"claim": "Flags detected", "value": list(flags), "source": src.from_addr if src else "thread", "quote": _snippets(src.body if src else texts, 1)})
    for a in actions[:3]:
        em = next((e for e in emails if e.id == a.email_id), None)
        evidence.append({"claim": f"Action: {a.type.value}", "value": a.description, "source": em.from_addr if em else "email", "quote": _snippets(em.body if em else "", 1)})
    audit = []
    for d in drafts:
        audit.append({
            "event": "draft",
            "status": d.status.value,
            "tone": d.tone,
            "sent_at": _iso(getattr(d, "sent_at", None)),
            "decision": d.auto_decision,
        })
    audit.append({"event": "analysis", "status": "generated", "engine": "Deal Intelligence v1 (heuristic, on-demand)"})

    return {
        "risk_radar": {"score": risk, "level": level, "reasons": reasons, "silence_days": silence_days, "next_best_actions": next_actions},
        "war_room": {"parties": parties, "intents": intents, "leverage": leverage, "suggested_moves": moves},
        "xray": {"documents_detected": doc_terms, "amounts": money, "dates_mentioned": dates, "promises_or_commitments": promises, "red_flags": red_flags, "note": "Text-scan of emails (attachments not deeply parsed)."},
        "operator": {"autonomous": False, "plan": operator_plan, "note": "Simulated operator plan; actions execute only with your approval/connected tools."},
        "provable": {"evidence": evidence, "audit_trail": audit},
    }
