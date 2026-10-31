from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import models


async def get_user_by_email(db: AsyncSession, email: str) -> models.User | None:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, name: str, email: str, role: models.RoleType = models.RoleType.agent
) -> models.User:
    user = models.User(name=name, email=email, role=role)
    db.add(user)
    await db.flush()
    return user


async def get_or_create_user(db: AsyncSession, name: str, email: str) -> models.User:
    user = await get_user_by_email(db, email)
    if user is None:
        user = await create_user(db, name, email)
    return user


async def add_email_account(
    db: AsyncSession,
    user_id,
    provider: models.ProviderType,
    email: str,
    scope: str = "",
    token_cache: str | None = None,
) -> models.EmailAccount:
    account = models.EmailAccount(
        user_id=user_id, provider=provider, email=email, scope=scope, token_cache=token_cache
    )
    db.add(account)
    await db.flush()
    return account


async def get_email_account(
    db: AsyncSession, user_id, provider: models.ProviderType
) -> models.EmailAccount | None:
    result = await db.execute(
        select(models.EmailAccount).where(
            models.EmailAccount.user_id == user_id,
            models.EmailAccount.provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def upsert_thread(
    db: AsyncSession,
    user_id,
    external_thread_id: str,
    subject: str,
    last_activity_at: datetime | None = None,
    category: models.CategoryType | None = None,
    priority_score: int | None = None,
    flags: list | None = None,
    summary: str | None = None,
    pipeline_hints: list | None = None,
) -> models.Thread:
    existing = await db.execute(
        select(models.Thread).where(
            models.Thread.user_id == user_id,
            models.Thread.thread_id == external_thread_id,
        )
    )
    thread = existing.scalar_one_or_none()
    if thread is None:
        thread = models.Thread(
            user_id=user_id,
            thread_id=external_thread_id,
            subject=subject,
        )
        db.add(thread)
    else:
        thread.subject = subject
    thread.last_sync_at = datetime.now(timezone.utc)
    thread.last_activity_at = last_activity_at or thread.last_activity_at
    if category is not None:
        thread.category = category
    if priority_score is not None:
        thread.priority_score = priority_score
    if flags is not None:
        thread.flags = flags
    if summary is not None:
        thread.summary = summary
    if pipeline_hints is not None:
        thread.pipeline_hints = pipeline_hints
    await db.flush()
    return thread


async def insert_email(
    db: AsyncSession,
    thread_id,
    message_id: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    received_at: datetime,
    has_attachment: bool = False,
    ai_summary: str | None = None,
    sentiment: dict | None = None,
) -> models.Email:
    email = models.Email(
        thread_id=thread_id,
        message_id=message_id,
        from_addr=from_addr,
        to_addr=to_addr,
        subject=subject,
        body=body,
        received_at=received_at,
        has_attachment=has_attachment,
        ai_summary=ai_summary,
        sentiment=sentiment,
    )
    db.add(email)
    await db.flush()
    return email


async def get_email_by_message_id(db: AsyncSession, message_id: str) -> models.Email | None:
    result = await db.execute(
        select(models.Email).where(models.Email.message_id == message_id)
    )
    return result.scalar_one_or_none()


async def add_draft(
    db: AsyncSession,
    email_id,
    text: str,
    tone: str = "",
    status: models.DraftStatus = models.DraftStatus.draft,
    auto_decision: dict | None = None,
) -> models.AiDraft:
    draft = models.AiDraft(
        email_id=email_id, text=text, tone=tone, status=status, auto_decision=auto_decision
    )
    db.add(draft)
    await db.flush()
    return draft


async def add_action_item(
    db: AsyncSession,
    email_id,
    type_: models.ActionType,
    description: str,
    due: datetime | None = None,
    contact: str | None = None,
    property: str | None = None,
) -> models.ActionItem:
    item = models.ActionItem(
        email_id=email_id,
        type=type_,
        description=description,
        due=due,
        contact=contact,
        property=property,
    )
    db.add(item)
    await db.flush()
    return item


async def list_threads_for_user(db: AsyncSession, user_id, limit: int = 100):
    result = await db.execute(
        select(models.Thread)
        .where(models.Thread.user_id == user_id)
        .order_by(models.Thread.last_activity_at.desc().nulls_last())
        .limit(limit)
    )
    return result.scalars().all()


async def get_thread_detail(db: AsyncSession, thread_id):
    return await db.get(models.Thread, thread_id)


async def list_emails_for_thread(db: AsyncSession, thread_id):
    result = await db.execute(
        select(models.Email)
        .where(models.Email.thread_id == thread_id)
        .order_by(models.Email.received_at.desc())
    )
    return result.scalars().all()


async def upsert_preferences(
    db: AsyncSession, user_id, tone_profile: dict | None = None, auto_features: dict | None = None, rules: str | None = None
) -> models.AgentPreference:
    result = await db.execute(
        select(models.AgentPreference).where(models.AgentPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = models.AgentPreference(user_id=user_id)
        db.add(pref)
    if tone_profile is not None:
        pref.tone_profile = tone_profile
    if auto_features is not None:
        pref.auto_features = auto_features
    if rules is not None:
        pref.rules = rules
    await db.flush()
    return pref


async def get_preferences(db: AsyncSession, user_id) -> models.AgentPreference | None:
    result = await db.execute(
        select(models.AgentPreference).where(models.AgentPreference.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def add_notification(
    db: AsyncSession,
    user_id,
    type_: models.NotificationType,
    title: str,
    body: str | None = None,
    thread_id=None,
    email_id=None,
) -> models.Notification:
    note = models.Notification(
        user_id=user_id,
        type=type_,
        title=title,
        body=body,
        thread_id=thread_id,
        email_id=email_id,
    )
    db.add(note)
    await db.flush()
    return note


async def list_notifications(
    db: AsyncSession, user_id, unread_only: bool = False, limit: int = 50
):
    stmt = select(models.Notification).where(models.Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(models.Notification.is_read.is_(False))
    stmt = stmt.order_by(models.Notification.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def mark_notification_read(db: AsyncSession, notification_id) -> models.Notification | None:
    note = await db.get(models.Notification, notification_id)
    if note is not None:
        note.is_read = True
        await db.flush()
    return note


async def get_user(db: AsyncSession, user_id) -> models.User | None:
    return await db.get(models.User, user_id)


async def upsert_subscription(
    db: AsyncSession,
    user_id,
    plan: models.PlanType,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    status: models.SubscriptionStatus,
    current_period_end: int | None = None,
) -> models.Subscription:
    if user_id:
        result = await db.execute(
            select(models.Subscription).where(models.Subscription.user_id == user_id)
        )
    else:
        result = await db.execute(
            select(models.Subscription).where(models.Subscription.stripe_customer_id == stripe_customer_id)
        )
    sub = result.scalar_one_or_none()
    if sub is None:
        sub = models.Subscription(user_id=user_id)
        db.add(sub)
    sub.plan = plan
    sub.stripe_customer_id = stripe_customer_id
    sub.stripe_subscription_id = stripe_subscription_id
    sub.status = status
    if current_period_end:
        from datetime import datetime, timezone
        sub.current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    else:
        sub.current_period_end = None
    await db.flush()
    return sub


async def get_active_subscription(db: AsyncSession, user_id) -> models.Subscription | None:
    result = await db.execute(
        select(models.Subscription)
        .where(models.Subscription.user_id == user_id)
        .where(models.Subscription.status.in_([
            models.SubscriptionStatus.active,
            models.SubscriptionStatus.trialing,
            models.SubscriptionStatus.past_due,
        ]))
    )
    return result.scalar_one_or_none()


async def count_emails_processed_this_month(
    db: AsyncSession, user_id, since: datetime
) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(models.Email.id))
        .join(models.Thread)
        .where(
            models.Thread.user_id == user_id,
            models.Email.ai_summary.is_not(None),
            models.Email.received_at >= since,
        )
    )
    return result.scalar() or 0


async def create_team(
    db: AsyncSession, owner_id, name: str
) -> models.Team:
    team = models.Team(name=name, owner_id=owner_id)
    db.add(team)
    await db.flush()
    # Add owner as admin member
    member = models.TeamMember(team_id=team.id, user_id=owner_id, role=models.TeamRole.admin)
    db.add(member)
    await db.flush()
    return team


async def get_team(db: AsyncSession, team_id) -> models.Team | None:
    return await db.get(models.Team, team_id)


async def get_user_teams(db: AsyncSession, user_id) -> list[models.Team]:
    result = await db.execute(
        select(models.Team)
        .join(models.TeamMember)
        .where(models.TeamMember.user_id == user_id)
    )
    return result.scalars().all()


async def get_team_members(db: AsyncSession, team_id) -> list[models.TeamMember]:
    result = await db.execute(
        select(models.TeamMember)
        .where(models.TeamMember.team_id == team_id)
        .options(selectinload(models.TeamMember.user))
    )
    return result.scalars().all()


async def add_team_member(
    db: AsyncSession, team_id, user_id, role: models.TeamRole = models.TeamRole.agent
) -> models.TeamMember:
    member = models.TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.add(member)
    await db.flush()
    return member


async def remove_team_member(db: AsyncSession, team_id, user_id) -> bool:
    result = await db.execute(
        select(models.TeamMember)
        .where(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member:
        await db.delete(member)
        await db.flush()
        return True
    return False


async def update_member_role(
    db: AsyncSession, team_id, user_id, role: models.TeamRole
) -> models.TeamMember | None:
    result = await db.execute(
        select(models.TeamMember)
        .where(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if member:
        member.role = role
        await db.flush()
    return member


async def deactivate_email_account(db: AsyncSession, email: str) -> bool:
    result = await db.execute(
        select(models.EmailAccount).where(models.EmailAccount.email == email)
    )
    account = result.scalar_one_or_none()
    if account:
        account.is_active = False
        await db.flush()
        return True
    return False