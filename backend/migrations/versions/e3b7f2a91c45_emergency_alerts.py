"""Add staff-managed emergency alerts.

Revision ID: e3b7f2a91c45
Revises: bc84a1d96f20
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3b7f2a91c45"
down_revision: Union[str, None] = "bc84a1d96f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "emergency_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("emergency_alerts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_emergency_alerts_is_active"), ["is_active"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("emergency_alerts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_emergency_alerts_is_active"))
    op.drop_table("emergency_alerts")