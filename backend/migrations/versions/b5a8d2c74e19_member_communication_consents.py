"""Add per-channel member communication consent.

Revision ID: b5a8d2c74e19
Revises: a73cc4125f06
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5a8d2c74e19"
down_revision: Union[str, None] = "a73cc4125f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_communication_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("is_consented", sa.Boolean(), nullable=False),
        sa.Column("consent_source", sa.String(length=32), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "channel", name="uq_member_communication_channel"),
    )
    with op.batch_alter_table("member_communication_consents", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_member_communication_consents_member_id"),
            ["member_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("member_communication_consents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_member_communication_consents_member_id"))
    op.drop_table("member_communication_consents")