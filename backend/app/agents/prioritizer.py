from app.agents.base import with_llm, base_system

CATEGORIES = [
    "lead", "client", "vendor", "legal", "financial",
    "internal", "spam", "newsletter",
]

FLAGS = [
    "hot_lead", "closing_deadline", "complaint", "follow_up",
    "pre_approved", "ready_to_list", "price_question", "needs_reply",
]


def score_email(email: dict, category: str, sentiment: dict | None = None, llm=None) -> dict:
    """Return {"score": 0-100, "urgency": str, "flags": [...]} for an email.

    score = how urgently the agent must act. spam/newsletter always score low.
    """
    llm = with_llm(llm)
    sent = sentiment or {}
    user = (
        "Scoring order for the agent's response: 100 = answer now, 0 = can ignore.\n"
        f"Allowed flags: {', '.join(FLAGS)}.\n"
        "Rules:\n"
        "- spam/newsletter/scoring: never above 30.\n"
        "- unread lead or client email: 65+.\n"
        "- explicit deadline (closing/inspection/offer): 85+ and flag closing_deadline.\n"
        "- 'pre-approved'/'ready to buy': flag pre_approved.\n"
        "- 'listing'/'ready to list': flag ready_to_list.\n"
        "- complaint or warning=True sentiment: flag complaint.\n"
        "- anything needing a reply: flag needs_reply.\n"
        "- urgency: one of [low, medium, high, critical].\n\n"
        "EMAIL:\n"
        + f"From: {email.get('from_addr', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Category: {category}\n"
        f"Sentiment: {sent}\n"
        f"Body: {email.get('body', '')[:4000]}\n"
        "\nReturn JSON: {\"score\": 0, \"urgency\": \"medium\", \"flags\": []}"
    )
    return llm(base_system("You are the Prioritizer agent."), user)