from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.db.session import get_session
from app.services import email_deliverability

router = APIRouter(prefix="/unsubscribe", tags=["unsubscribe"])


@router.get("", response_class=HTMLResponse)
async def unsubscribe_page(
    request: Request,
    email: str,
    user_id: str,
    token: str,
    db: AsyncSession = Depends(get_session),
):
    """Display unsubscribe confirmation page."""
    valid = email_deliverability.verify_unsubscribe_token(token, email, user_id)

    if not valid:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Invalid Unsubscribe Link</title></head>
                <body style="font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px;">
                    <h1>Invalid or Expired Link</h1>
                    <p>This unsubscribe link is invalid or has expired.</p>
                    <p>If you believe this is an error, please contact support.</p>
                </body>
            </html>
            """,
            status_code=400,
        )

    return HTMLResponse(
        content=f"""
        <html>
            <head>
                <title>Unsubscribe from Smart Inbox</title>
                <style>
                    body {{ font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    .btn {{ background: #dc2626; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }}
                    .btn:hover {{ background: #b91c1c; }}
                    .email {{ background: #f3f4f6; padding: 12px; border-radius: 6px; margin: 16px 0; }}
                </style>
            </head>
            <body>
                <h1>Unsubscribe from Smart Inbox</h1>
                <p>You are about to unsubscribe <strong>{email}</strong> from Smart Inbox.</p>
                <p>This will disconnect Gmail and stop all email processing for this account.</p>
                <form method="POST" action="/unsubscribe">
                    <input type="hidden" name="email" value="{email}">
                    <input type="hidden" name="user_id" value="{user_id}">
                    <input type="hidden" name="token" value="{token}">
                    <button type="submit" class="btn">Confirm Unsubscribe</button>
                </form>
                <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                    If you didn't request this, you can ignore this email. Your account will remain active.
                </p>
            </body>
        </html>
        """
    )


@router.post("", response_class=HTMLResponse)
async def unsubscribe_confirm(
    request: Request,
    email: str = Form(...),
    user_id: str = Form(...),
    token: str = Form(...),
    db: AsyncSession = Depends(get_session),
):
    """Process unsubscribe confirmation."""
    result = await email_deliverability.handle_unsubscribe(db, email, user_id, token)

    if result["success"]:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Unsubscribed Successfully</title></head>
                <body style="font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px;">
                    <h1>Unsubscribed Successfully</h1>
                    <p>Your account has been disconnected from Smart Inbox.</p>
                    <p>You will no longer receive emails or notifications from us.</p>
                    <p>If you change your mind, you can always sign up again at <a href="/">Smart Inbox</a>.</p>
                </body>
            </html>
            """
        )
    else:
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Unsubscribe Failed</title></head>
                <body style="font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px;">
                    <h1>Unsubscribe Failed</h1>
                    <p>Error: {result.get('error', 'Unknown error')}</p>
                    <p>Please contact support if this issue persists.</p>
                </body>
            </html>
            """,
            status_code=400,
        )


@router.post("/bounce")
async def handle_bounce(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Handle bounce webhook from email provider (e.g., SendGrid, AWS SES)."""
    try:
        bounce_data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    result = await email_deliverability.process_bounce(db, bounce_data)
    return result