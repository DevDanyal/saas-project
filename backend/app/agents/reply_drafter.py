from app.agents.base import with_llm, base_system, CLIENT_COMMS_SKILL


def draft_reply(thread: list[dict], tone_profile: dict | None = None, rules: str | None = None, llm=None) -> dict:
    """Return {"reply_text", "suggested_tone"} for the most recent email.

    thread: chronologically ordered emails of the thread (oldest first);
           the last one is the one being replied to.
    tone_profile: from agent preferences, e.g. {"style": "friendly"}.
    rules: agent personal rules, e.g. "no price promises".
    """
    llm = with_llm(llm)
    tone = tone_profile or {}
    thread_lines = []
    for i, m in enumerate(thread[-6:], start=1):
        thread_lines.append(
            f"[{i}] From: {m.get('from_addr', '')} | {m.get('received_at', '')}\n"
            f"Subject: {m.get('subject', '')}\n{m.get('body', '')[:1500]}"
        )
    user = (
        "Draft a reply for the real estate agent to the latest message in this thread.\n"
        + CLIENT_COMMS_SKILL
        + f"\n\nAgent tone profile: {tone}\n"
        f"Agent rules: {rules or 'none'}\n\nTHREAD LATEST 6:\n"
        + "\n\n---\n\n".join(thread_lines)
        + "\n\nReturn JSON: {\"reply_text\": \"...\", \"suggested_tone\": \"friendly|formal|urgent\"}"
    )
    return llm(base_system("You are the Reply Drafter agent."), user)