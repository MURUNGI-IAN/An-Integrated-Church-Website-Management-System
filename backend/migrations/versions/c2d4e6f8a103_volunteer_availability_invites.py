"""Add one-use volunteer availability links.

Revision ID: c2d4e6f8a103
Revises: f17a0be96231
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d4e6f8a103"
down_revision: Union[str, None] = "f17a0be96231"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("volunteer_availability", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_by_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

    op.create_table(
        "availability_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("availability_invites", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_availability_invites_member_id"), ["member_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_availability_invites_token_digest"), ["token_digest"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("availability_invites", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_availability_invites_token_digest"))
        batch_op.drop_index(batch_op.f("ix_availability_invites_member_id"))
    op.drop_table("availability_invites")
    with op.batch_alter_table("volunteer_availability", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_by_id",
            existing_type=sa.Integer(),
            nullable=False,
        )