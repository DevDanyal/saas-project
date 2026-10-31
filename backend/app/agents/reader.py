"""Reader agent: normalize a raw email into a clean, structured record.

Header extraction itself is deterministic (gmail_sync does it); this agent
produces body_clean (quotes/signatures stripped where sensible), reply_depth,
and a short summary so downstream agents see tidy input.
"""

from app.agents.base import with_llm, base_system


def read_email(email: dict, llm=None) -> dict:
    """Return {from,to,subject,received_at,body_clean,thread_id,has_attachment,reply_depth}."""
    llm = with_llm(llm)
    user = (
        "Normalize this raw email for downstream agents.\n"
        "- body_clean: same content with quotes, signatures, and forwarded noise removed.\n"
        "- reply_depth: 0 if original, 1 if it replies once, 2+ for deeper threads.\n"
        "- Keep has_attachment and all header fields as-is.\n\n"
        "RAW EMAIL:\n"
        + f"from_addr: {email.get('from_addr', '')}\n"
        f"to_addr: {email.get('to_addr', '')}\n"
        f"subject: {email.get('subject', '')}\n"
        f"received_at: {email.get('received_at', '')}\n"
        f"thread_id: {email.get('thread_id', '')}\n"
        f"has_attachment: {email.get('has_attachment', False)}\n"
        f"body:\n{email.get('body', '')[:6000]}\n"
        "\nReturn JSON: {\"from\":\"\",\"to\":\"\",\"subject\":\"\",\"received_at\":\"\","
        "\"body_clean\":\"\",\"thread_id\":\"\",\"has_attachment\":false,\"reply_depth\":0}"
    )
    return llm(base_system("You are the Reader agent."), user)