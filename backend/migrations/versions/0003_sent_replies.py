"""phase 4b: track sent replies

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_drafts", sa.Column("sent_message_id", sa.String(length=255), nullable=True))
    op.add_column("ai_drafts", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_drafts", "sent_at")
    op.drop_column("ai_drafts", "sent_message_id")