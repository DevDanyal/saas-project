"""add daily digests

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_digests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest_date", sa.Date(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "digest_date", name="uq_daily_digest"),
    )
    op.create_index("ix_daily_digests_user_id", "daily_digests", ["user_id"])
    op.create_index("ix_daily_digests_digest_date", "daily_digests", ["digest_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_digests_digest_date", table_name="daily_digests")
    op.drop_index("ix_daily_digests_user_id", table_name="daily_digests")
    op.drop_table("daily_digests")
