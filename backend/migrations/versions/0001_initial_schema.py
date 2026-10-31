"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("oauth_tokens", sa.Text(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("admin", "agent", name="role_type", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "email_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("gmail", "outlook", name="provider_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.Text(), server_default="", nullable=False),
        sa.Column("token_cache", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_email_account_user_provider"),
    )
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])

    op.create_table(
        "threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=1024), server_default="", nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "lead",
                "client",
                "vendor",
                "legal",
                "financial",
                "internal",
                "spam",
                "newsletter",
                name="category_type",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("priority_score", sa.Integer(), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "thread_id", name="uq_thread_user_external"),
    )
    op.create_index("ix_threads_last_activity_at", "threads", ["last_activity_at"])
    op.create_index("ix_threads_user_id", "threads", ["user_id"])

    op.create_table(
        "emails",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("from_addr", sa.String(length=255), nullable=False),
        sa.Column("to_addr", sa.String(length=1024), server_default="", nullable=False),
        sa.Column("subject", sa.String(length=1024), server_default="", nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.JSON(), nullable=True),
        sa.Column("has_attachment", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emails_message_id", "emails", ["message_id"], unique=True)
    op.create_index("ix_emails_received_at", "emails", ["received_at"])
    op.create_index("ix_emails_thread_id", "emails", ["thread_id"])

    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=64), server_default="", nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "edited", "sent", "rejected", name="draft_status", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_drafts_email_id", "ai_drafts", ["email_id"])

    op.create_table(
        "action_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "call", "calendar", "todo", "email", "follow_up", name="action_type", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("property", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "done", "cancelled", name="action_status", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_items_email_id", "action_items", ["email_id"])

    op.create_table(
        "agent_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tone_profile", sa.JSON(), nullable=True),
        sa.Column("auto_features", sa.JSON(), nullable=True),
        sa.Column("rules", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_preferences_user_id", "agent_preferences", ["user_id"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", "team", name="plan_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active", "canceled", "past_due", "trialing", "incomplete",
                name="subscription_status", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_agent_preferences_user_id", table_name="agent_preferences")
    op.drop_table("agent_preferences")
    op.drop_index("ix_action_items_email_id", table_name="action_items")
    op.drop_table("action_items")
    op.drop_index("ix_ai_drafts_email_id", table_name="ai_drafts")
    op.drop_table("ai_drafts")
    op.drop_index("ix_emails_thread_id", table_name="emails")
    op.drop_index("ix_emails_received_at", table_name="emails")
    op.drop_index("ix_emails_message_id", table_name="emails")
    op.drop_table("emails")
    op.drop_index("ix_threads_user_id", table_name="threads")
    op.drop_index("ix_threads_last_activity_at", table_name="threads")
    op.drop_table("threads")
    op.drop_index("ix_email_accounts_user_id", table_name="email_accounts")
    op.drop_table("email_accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")