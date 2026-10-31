"""Send replies through the Gmail API."""

import base64
from email.message import EmailMessage


def build_raw_message(
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
) -> dict:
    """Build a base64url-encoded RFC 2822 message for Gmail's send endpoint."""
    msg = EmailMessage()
    if from_addr:
        msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body or "")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {"raw": raw}


def send_reply(
    service,
    to_addr: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    from_addr: str | None = None,
) -> dict:
    """Send a reply and keep it in the original Gmail thread when possible."""
    payload = build_raw_message(to_addr, subject, body, from_addr=from_addr)
    if thread_id:
        payload["threadId"] = thread_id
    return service.users().messages().send(userId="me", body=payload).execute()
