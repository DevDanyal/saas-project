from app.agents.base import with_llm, base_system

CATEGORIES = [
    "lead", "client", "vendor", "legal", "financial",
    "internal", "spam", "newsletter",
]

_CATEGORY_GUIDE = """
lead: a potential buyer/seller not yet working with the agent.
client: an active buyer/seller under contract or in active process.
vendor: home inspectors, photographers, title, mortgage, stagers, contractors.
legal: lawyers, disputes, contracts, requests for legal advice.
financial: financing, pre-approvals, mortgage, closing costs, currency.
internal: from the agent's own team, brokerage, or tools.
spam: promotions/unsolicited bulk mail, scams, phishing.
newsletter: legitimate subscriptions/digests/bulk marketing.
"""

_EXAMPLES = """
Examples:
- "Hi, we are pre-approved for $450k and want to see lakefront homes." -> lead
- "The appraisal report is ready for the closing file." -> client
- "Inspection scheduled for Thursday at the Smith listing." -> vendor
- "Please review the attached purchase agreement." -> legal
- "Wire instructions for the earnest money deposit..." -> financial
- "Team meeting moved to 10am." -> internal
- "Congratulations! You've won a prize..." -> spam
- "Your monthly market report is here." -> newsletter
"""


_ALIASES = {
    "customer": "client",
    "customers": "client",
    "buyer": "client",
    "buyers": "client",
    "seller": "client",
    "sellers": "client",
    "active_client": "client",
    "leads": "lead",
    "prospect": "lead",
    "prospects": "lead",
    "buyer_lead": "lead",
    "seller_lead": "lead",
    "vendors": "vendor",
    "inspector": "vendor",
    "inspectors": "vendor",
    "contractor": "vendor",
    "contractors": "vendor",
    "lawyer": "legal",
    "lawyers": "legal",
    "attorney": "legal",
    "attorneys": "legal",
    "finance": "financial",
    "mortgage": "financial",
    "billing": "financial",
    "team": "internal",
    "company": "internal",
    "office": "internal",
    "promotion": "spam",
    "junk": "spam",
    "phishing": "spam",
    "marketing": "newsletter",
    "subscription": "newsletter",
    "digest": "newsletter",
}

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("spam", (
        "you'v won", "you won", "prize", "lottery", "phishing", "crypto",
        "viagra", "click here to claim", "act now", "risk-free",
    )),
    ("newsletter", (
        "unsubscribe", "newsletter", "daily digest", "weekly digest",
        "market report", "linkedin", "pinterest", "people you may know",
        "view in browser", "manage preferences",
    )),
    ("legal", (
        "attorney", "lawyer", "legal", "purchase agreement", "contract",
        "disclosure", "addendum", "attached agreement", "escrow instructions",
    )),
    ("financial", (
        "mortgage", "pre-approved", "pre approved", "preapproval", "loan",
        "wire instructions", "earnest money", "closing cost", "escrow",
        "apr", "interest rate", "down payment",
    )),
    ("vendor", (
        "inspection", "inspector", "photographer", "staging", "appraiser",
        "appraisal report", "contractor", "title company", "handyman",
    )),
    ("lead", (
        "interested in", "schedule a showing", "see the home", "book a tour",
        "looking to buy", "looking to sell", "listing alert", "pre-approved for",
    )),
    ("client", (
        "under contract", "offer accepted", "closing date", "final walkthrough",
        "counteroffer", "counter offer", "closing disclosure",
    )),
    ("internal", (
        "team meeting", "our brokerage", "internal", "office", "staff",
    )),
]


def normalize_category(value) -> str | None:
    """Coerce model output like 'Lead', 'Customers', 'FINANCE' to a valid category."""
    if value is None:
        return None
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if key in CATEGORIES:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    for category in CATEGORIES:
        if category in key:
            return category
    return None


def fallback_category(email: dict) -> str:
    """Deterministic keyword classifier used when the LLM is unavailable.

    Guarantees every email lands in a section so the inbox keeps separating
    mail even during provider outages or rate limits.
    """
    text = " ".join(
        [
            str(email.get("subject", "")),
            str(email.get("from_addr", "")),
            str(email.get("body", ""))[:4000],
        ]
    ).lower()
    for category, keywords in _KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "internal"


def classify_email(email: dict, llm=None) -> dict:
    """Return {"category": one of CATEGORIES} for a cleaned email."""
    llm = with_llm(llm)
    user = (
        "Classify this email thread into exactly one category.\n"
        + _CATEGORY_GUIDE
        + _EXAMPLES
        + "\n\nEMAIL:\n"
        + f"From: {email.get('from_addr', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Body: {email.get('body', '')[:4000]}\n"
        "\nReturn JSON: {\"category\": \"<one of the categories>\"}"
    )
    return llm(base_system("You are the Categorizer agent."), user)