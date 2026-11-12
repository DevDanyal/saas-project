"""Knowledge MCP — agent preferences, tone profile, response templates, decisions.

Backed by ``AgentPreference`` (tone/rules/features) and ``KnowledgeEntry``
(templates/decisions). Safe, read-mostly helpers used by the AI pipeline.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models


DEFAULT_TEMPLATES = [
    {
        "name": "lead_intro",
        "subject": "Thanks for reaching out — let's find your home",
        "body": "Hi {{name}}, congrats on your pre-approval! I'd love to schedule a quick call to learn what you're looking for.",
    },
    {
        "name": "showing_confirmation",
        "subject": "Showing confirmed — {{property}}",
        "body": "Hi {{name}}, confirming your showing at {{property}} on {{time}}. Reply if you need to reschedule.",
    },
    {
        "name": "closing_reminder",
        "subject": "Closing timeline reminder",
        "body": "Hi {{name}}, a quick reminder of the upcoming closing steps and dates. Let me know if anything changes.",
    },
]


async def get_agent_preferences(db: AsyncSession, user_id) -> dict:
    pref = await crud.get_preferences(db, user_id)
    if pref is None:
        return {"tone_profile": {}, "auto_features": {}, "rules": None}
    return {
        "tone_profile": pref.tone_profile or {},
        "auto_features": pref.auto_features or {},
        "rules": pref.rules,
    }


async def get_tone_profile(db: AsyncSession, user_id) -> dict:
    prefs = await get_agent_preferences(db, user_id)
    return prefs.get("tone_profile") or {}


async def get_response_templates(db: AsyncSession, user_id) -> list[dict]:
    rows = await crud.list_knowledge_entries(db, user_id, "template")
    templates = [r.value for r in rows if isinstance(r.value, dict)]
    return templates or [dict(t) for t in DEFAULT_TEMPLATES]


async def save_response_template(db: AsyncSession, user_id, name: str, template: dict) -> dict:
    await crud.upsert_knowledge_entry(db, user_id, "template", name, template)
    return {"success": True, "name": name}


async def remember_decision(db: AsyncSession, user_id, key: str, decision: Any) -> dict:
    """Persist a decision the agent made so future drafts stay consistent."""
    await crud.upsert_knowledge_entry(db, user_id, "decision", key, {"decision": decision})
    return {"success": True, "key": key}


async def recall_decisions(db: AsyncSession, user_id) -> list[dict]:
    rows = await crud.list_knowledge_entries(db, user_id, "decision")
    return [{"key": r.key, "value": r.value} for r in rows]


# MCP tool definitions
KNOWLEDGE_TOOLS = [
    {"name": "get_agent_preferences", "description": "Fetch the agent's preferences (tone, rules, auto features)", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
    {"name": "get_tone_profile", "description": "Fetch the agent's tone profile", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
    {"name": "get_response_templates", "description": "Fetch reusable reply templates", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
    {"name": "remember_decision", "description": "Remember a decision for future consistency", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}, "key": {"type": "string"}, "decision": {}}, "required": ["user_id", "key", "decision"]}},
]


async def handle_knowledge_tool_call(name: str, arguments: dict, db: AsyncSession) -> dict:
    import uuid

    user_id = uuid.UUID(arguments["user_id"])
    if name == "get_agent_preferences":
        return await get_agent_preferences(db, user_id)
    if name == "get_tone_profile":
        return await get_tone_profile(db, user_id)
    if name == "get_response_templates":
        return {"templates": await get_response_templates(db, user_id)}
    if name == "remember_decision":
        return await remember_decision(db, user_id, arguments["key"], arguments["decision"])
    raise ValueError(f"Unknown knowledge tool: {name}")
