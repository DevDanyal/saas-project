import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/team/{team_id}")
async def team_report(
    team_id: uuid.UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_session),
):
    """Generate team activity report for the last N days."""
    team = await crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    member_ids = [m.user_id for m in team.members]

    # Emails processed per member
    emails_result = await db.execute(
        select(models.User.email, func.count(models.Email.id))
        .join(models.Thread, models.Thread.user_id == models.User.id)
        .join(models.Email, models.Email.thread_id == models.Thread.id)
        .where(
            models.User.id.in_(member_ids),
            models.Email.ai_summary.is_not(None),
            models.Email.received_at >= cutoff,
        )
        .group_by(models.User.email)
    )
    emails_by_member = {email: count for email, count in emails_result.all()}

    # Action items per member
    actions_result = await db.execute(
        select(models.User.email, func.count(models.ActionItem.id))
        .join(models.Email, models.Email.id == models.ActionItem.email_id)
        .join(models.Thread, models.Thread.id == models.Email.thread_id)
        .join(models.User, models.User.id == models.Thread.user_id)
        .where(
            models.User.id.in_(member_ids),
            models.ActionItem.created_at >= cutoff,
        )
        .group_by(models.User.email)
    )
    actions_by_member = {email: count for email, count in actions_result.all()}

    # Categories breakdown
    categories_result = await db.execute(
        select(models.Thread.category, func.count(models.Thread.id))
        .where(
            models.Thread.user_id.in_(member_ids),
            models.Thread.last_activity_at >= cutoff,
        )
        .group_by(models.Thread.category)
    )
    categories = {cat.value if cat else "uncategorized": count for cat, count in categories_result.all()}

    # Priority distribution
    priority_result = await db.execute(
        select(
            func.count(models.Thread.id).filter(models.Thread.priority_score >= 80),
            func.count(models.Thread.id).filter(models.Thread.priority_score >= 50),
            func.count(models.Thread.id).filter(models.Thread.priority_score < 50),
        )
        .where(
            models.Thread.user_id.in_(member_ids),
            models.Thread.last_activity_at >= cutoff,
        )
    )
    high, medium, low = priority_result.one()

    # Notifications
    notifications_result = await db.execute(
        select(models.Notification.type, func.count(models.Notification.id))
        .where(
            models.Notification.user_id.in_(member_ids),
            models.Notification.created_at >= cutoff,
        )
        .group_by(models.Notification.type)
    )
    notifications = {n_type.value: count for n_type, count in notifications_result.all()}

    return {
        "team_id": str(team_id),
        "team_name": team.name,
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "members_count": len(member_ids),
        "emails_processed": {
            "total": sum(emails_by_member.values()),
            "by_member": emails_by_member,
        },
        "actions_created": {
            "total": sum(actions_by_member.values()),
            "by_member": actions_by_member,
        },
        "categories": categories,
        "priority_distribution": {
            "high": high,
            "medium": medium,
            "low": low,
        },
        "notifications": notifications,
    }