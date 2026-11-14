"""add email read state

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-13

"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing databases may already have the column (created via create_all),
    # so make this safe to apply either way.
    op.execute(
        "ALTER TABLE emails "
        "ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE emails DROP COLUMN IF EXISTS is_read")
