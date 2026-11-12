"""add knowledge entries

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("value", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("user_id", "kind", "key", name="uq_knowledge_entry"),
    )
    op.create_index("ix_knowledge_entries_user_id", "knowledge_entries", ["user_id"])
    op.create_index("ix_knowledge_entries_kind", "knowledge_entries", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_entries_kind", table_name="knowledge_entries")
    op.drop_index("ix_knowledge_entries_user_id", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
