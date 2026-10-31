from app.agents.base import with_llm, base_system

DIGEST_FORMAT_SKILL = """
Format the morning brief as one scannable page using markdown.
- Opening line: the whole day in one sentence.
- Sections in order: Hot leads, Closings & deadlines, Overdue follow-ups, Other.
- One bullet per item, max ~15 words, plain language, no invented facts.
- Never include spam or newsletter items.
- Never quote prices, financing numbers, or legal terms as the agent's fact.
- The agent skims this in 30 seconds: no paragraphs, no repetition.
"""

_PRIORITY_SORT = {
    "critical": 0, "high": 1, "medium": 2, "low": 3,
}


def _threads_block(threads: list[dict]) -> str:
    if not threads:
        return "(no active threads)"
    lines = []
    for t in sorted(threads, key=lambda x: x.get("priority_score", 0) or 0, reverse=True):
        lines.append(
            f"- [{t.get('priority_score')}] {t.get('subject', '')} "
            f"| {t.get('category', '')} | {t.get('summary', '')}"
        )
    return "\n".join(lines)


def _actions_block(actions: list[dict]) -> str:
    if not actions:
        return "(no open action items)"
    lines = []
    for a in actions:
        lines.append(
            f"- {a.get('type', '')}: {a.get('description', '')} "
            f"| due {a.get('due') or 'no date'} | {a.get('contact', '')}"
        )
    return "\n".join(lines)


def build_digest(threads: list[dict], actions: list[dict], llm=None) -> dict:
    """Return {"brief": "...", "sections": {"hot_leads": [...], ...}} for the morning brief."""
    llm = with_llm(llm)
    user = (
        "Build the agent's morning brief from today's inbox state.\n"
        f"\n### Active threads (last 24h)\n{_threads_block(threads)}\n"
        f"\n### Open action items\n{_actions_block(actions)}\n"
        "\nReturn JSON: {\"brief\": \"opening sentence\", "
        "\"sections\": {\"hot_leads\": [], \"closings\": [], \"follow_ups\": [], \"other\": []}}"
    )
    return llm(base_system("You are the Digest agent.\n\n" + DIGEST_FORMAT_SKILL.strip()), user)