"""add digest notification type

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.create_check_constraint(
            "notification_type",
            "type IN ('hot_lead', 'urgent', 'closing', 'complaint', 'digest')",
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("notification_type", type_="check")