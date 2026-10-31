"""Agent base helpers and product skills shared by every sub-agent.

The compliance skill is always loaded — it is the safety guardrail and
must not be dropped from any agent's system prompt.
"""

from app.services.llm import generate_json

ASSURE_JSON = "Respond with raw JSON only. No markdown, no code fences, no commentary."

DOMAIN_SKILL = """
You work in real estate. Know: buyer/seller agent vocabulary, contracts,
inspections, closing timelines, MLS jargon, mortgage terms, showings and
open houses. A "lead" is a potential buyer or seller. A "client" is already
under contract or actively working with the agent.
"""

COMPLIANCE_SKILL = """
NEVER, under any circumstances, do any of these:
- Quote, negotiate, or promise a price/financing/APR/loan terms.
- Promise a specific closing date or legal outcome.
- Act as a lawyer, title agent, or mortgage broker.
- Send anything on the agent's behalf without an explicit confirm step.
When in doubt, flag it for the agent instead of answering.
"""

CLIENT_COMMS_SKILL = """
Reply drafts must match the agent's profile tone, stay professional and warm,
never invent facts or numbers, never commit the agent to something not in the
email, and always leave a clear next step for the agent to confirm.
"""


def base_system(extra: str = "") -> str:
    parts = [
        "You are a sub-agent of an AI inbox assistant for real estate agents.",
        DOMAIN_SKILL.strip(),
        COMPLIANCE_SKILL.strip(),
        ASSURE_JSON,
    ]
    if extra:
        parts.insert(3, extra.strip())
    return "\n\n".join(parts)


def with_llm(llm=None):
    """Return the LLM callable, defaulting to the production client."""
    return llm or generate_json