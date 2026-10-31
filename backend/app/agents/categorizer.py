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