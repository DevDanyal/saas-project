"""Lead pipeline hints: turn agent flags into human-readable buyer/seller signals.

Deterministic (no extra LLM call) so it is free and consistent.
"""

HINT_LABELS = {
    "pre_approved": "Buyer pre-approved",
    "ready_to_list": "Seller ready to list",
    "hot_lead": "Hot lead",
    "price_question": "Price-sensitive",
    "closing_deadline": "Closing soon",
    "complaint": "At-risk client",
    "follow_up": "Follow-up due",
    "needs_reply": "Needs reply",
}

BUYER_SIGNALS = {"pre_approved", "hot_lead", "price_question"}
SELLER_SIGNALS = {"ready_to_list"}


def derive_hints(category: str | None, flags: list | None) -> list[str]:
    """Return a de-duplicated, ordered list of hint labels for a thread."""
    hints: list[str] = []
    for flag in flags or []:
        label = HINT_LABELS.get(flag)
        if label and label not in hints:
            hints.append(label)

    if category == "lead" and "Hot lead" not in hints and not hints:
        hints.append("New lead")

    return hints


def pipeline_side(category: str | None, flags: list | None) -> str | None:
    """Return 'buyer', 'seller', or None based on the strongest signal."""
    fset = set(flags or [])
    if fset & SELLER_SIGNALS:
        return "seller"
    if fset & BUYER_SIGNALS or category == "lead":
        return "buyer"
    return None