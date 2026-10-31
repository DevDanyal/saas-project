from app.agents.base import with_llm, base_system

_MOOD_GUIDE = """
mood: one of ["positive", "neutral", "negative", "urgent"] describing the
     writer's dominant tone toward the agent.
intensity: float 0.0-1.0, how strongly that mood is felt.
warning: true when the client seems anxious, angry, or at risk of churn —
     flag emotional distress even if the words are polite.
"""


def analyze_sentiment(email: dict, llm=None) -> dict:
    """Return {"mood", "intensity", "warning"} for a cleaned email."""
    llm = with_llm(llm)
    user = (
        "Read the email and assess the writer's sentiment for a real estate agent.\n"
        + _MOOD_GUIDE
        + "\n\nEMAIL:\n"
        + f"From: {email.get('from_addr', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Body: {email.get('body', '')[:4000]}\n"
        "\nReturn JSON: {\"mood\": \"...\", \"intensity\": 0.0, \"warning\": false}"
    )
    return llm(base_system("You are the Sentiment agent."), user)