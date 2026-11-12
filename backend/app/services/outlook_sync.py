"""Microsoft Graph / Outlook integration (Phase 4).

Skeleton only: token acquisition and inbox sync are not yet wired. The
service raises a clear error so callers can fall back to Gmail.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class OutlookNotConfigured(Exception):
    pass


async def sync_user_inbox(db: AsyncSession, user_id: UUID, max_results: int = 20) -> dict:
    raise OutlookNotConfigured(
        "Outlook/Microsoft Graph sync is not implemented yet. "
        "Connect a Gmail account instead."
    )
