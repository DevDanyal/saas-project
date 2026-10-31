from app.agents.base import with_llm, base_system

ACTION_TYPES = ["call", "calendar", "todo", "email", "follow_up"]


def extract_actions(email: dict, category: str, llm=None) -> dict:
    """Return {"actions": [{type, description, due, contact, property}]}.

    type must be one of: call, calendar, todo, email, follow_up.
    due: ISO datetime when known, else empty string.
    Only extract actions the email actually implies; empty list is valid.
    """
    llm = with_llm(llm)
    user = (
        "Extract every action the agent must take from this email.\n"
        f"Allowed types: {', '.join(ACTION_TYPES)}.\n"
        "- due: ISO-8601 or empty string if no deadline is named.\n"
        "- contact: sender or named third party.\n"
        "- property: address/listing if mentioned.\n"
        "Do NOT invent actions. If none, return an empty list.\n\n"
        "EMAIL:\n"
        + f"From: {email.get('from_addr', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Category: {category}\n"
        f"Body: {email.get('body', '')[:4000]}\n"
        "\nReturn JSON: {\"actions\": []}"
    )
    return llm(base_system("You are the Action Extractor agent."), user)