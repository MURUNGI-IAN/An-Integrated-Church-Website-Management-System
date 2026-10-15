"""Record expense reviewers and pledge fulfillment amounts.

Revision ID: a2b3c4d5e6f7
Revises: 3e7f9a1c5b20
Create Date: 2026-10-15 14:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "3e7f9a1c5b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("finance_entries") as batch_op:
        batch_op.alter_column("approved_by_id", new_column_name="reviewed_by_id")
        batch_op.alter_column("approved_at", new_column_name="reviewed_at")
    with op.batch_alter_table("finance_pledges") as batch_op:
        batch_op.add_column(sa.Column("amount_fulfilled_ugx", sa.Integer(), nullable=False, server_default="0"))
        batch_op.alter_column("amount_fulfilled_ugx", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("finance_pledges") as batch_op:
        batch_op.drop_column("amount_fulfilled_ugx")
    with op.batch_alter_table("finance_entries") as batch_op:
        batch_op.alter_column("reviewed_at", new_column_name="approved_at")
        batch_op.alter_column("reviewed_by_id", new_column_name="approved_by_id")
