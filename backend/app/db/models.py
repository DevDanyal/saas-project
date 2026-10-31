import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoleType(str, enum.Enum):
    admin = "admin"
    agent = "agent"


class ProviderType(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"


class CategoryType(str, enum.Enum):
    lead = "lead"
    client = "client"
    vendor = "vendor"
    legal = "legal"
    financial = "financial"
    internal = "internal"
    spam = "spam"
    newsletter = "newsletter"


class ActionType(str, enum.Enum):
    call = "call"
    calendar = "calendar"
    todo = "todo"
    email = "email"
    follow_up = "follow_up"


class DraftStatus(str, enum.Enum):
    draft = "draft"
    edited = "edited"
    sent = "sent"
    rejected = "rejected"


class ActionStatus(str, enum.Enum):
    open = "open"
    done = "done"
    cancelled = "cancelled"


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"
    team = "team"


class NotificationType(str, enum.Enum):
    hot_lead = "hot_lead"
    urgent = "urgent"
    closing = "closing"
    complaint = "complaint"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    canceled = "canceled"
    past_due = "past_due"
    trialing = "trialing"
    incomplete = "incomplete"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    oauth_tokens: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[RoleType] = mapped_column(
        Enum(RoleType, name="role_type", native_enum=False), default=RoleType.agent
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    email_accounts: Mapped[list["EmailAccount"]] = relationship(back_populates="user")
    threads: Mapped[list["Thread"]] = relationship(back_populates="user")
    preferences: Mapped["AgentPreference | None"] = relationship(
        back_populates="user", uselist=False
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    team_memberships: Mapped[list["TeamMember"]] = relationship(back_populates="user")
    owned_teams: Mapped[list["Team"]] = relationship(back_populates="owner", foreign_keys="Team.owner_id")


class EmailAccount(Base):
    __tablename__ = "email_accounts"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_email_account_user_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, name="provider_type", native_enum=False)
    )
    email: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(Text, default="")
    token_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="email_accounts")


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (UniqueConstraint("user_id", "thread_id", name="uq_thread_user_external"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(1024), default="")
    category: Mapped[CategoryType | None] = mapped_column(
        Enum(CategoryType, name="category_type", native_enum=False), nullable=True
    )
    priority_score: Mapped[int | None] = mapped_column(nullable=True)
    flags: Mapped[list | dict] = mapped_column(JSON, default=list)
    pipeline_hints: Mapped[list | dict] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="threads")
    emails: Mapped[list["Email"]] = relationship(back_populates="thread")


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id"), index=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    from_addr: Mapped[str] = mapped_column(String(255))
    to_addr: Mapped[str] = mapped_column(String(1024), default="")
    subject: Mapped[str] = mapped_column(String(1024), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, server_default=func.now()
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    has_attachment: Mapped[bool] = mapped_column(default=False)

    thread: Mapped[Thread] = relationship(back_populates="emails")
    drafts: Mapped[list["AiDraft"]] = relationship(back_populates="email")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="email")


class AiDraft(Base):
    __tablename__ = "ai_drafts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status", native_enum=False), default=DraftStatus.draft
    )
    auto_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped[Email] = relationship(back_populates="drafts")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("emails.id"), index=True)
    type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, name="action_type", native_enum=False)
    )
    description: Mapped[str] = mapped_column(Text)
    due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    property: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus, name="action_status", native_enum=False), default=ActionStatus.open
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    email: Mapped[Email] = relationship(back_populates="action_items")


class AgentPreference(Base):
    __tablename__ = "agent_preferences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    tone_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    auto_features: Mapped[dict] = mapped_column(JSON, default=dict)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="preferences")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType, name="plan_type", native_enum=False), default=PlanType.free
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", native_enum=False),
        default=SubscriptionStatus.trialing,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="subscriptions")


class TeamRole(str, enum.Enum):
    admin = "admin"
    agent = "agent"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[TeamRole] = mapped_column(
        Enum(TeamRole, name="team_role", native_enum=False), default=TeamRole.agent
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("threads.id"), nullable=True)
    email_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("emails.id"), nullable=True)
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=False)
    )
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )