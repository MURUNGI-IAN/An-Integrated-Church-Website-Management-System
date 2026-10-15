"""Add encrypted member registry

Revision ID: 9ac7bf120e3d
Revises: 46fb64470c0e
Create Date: 2026-10-14 15:24:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9ac7bf120e3d"
down_revision: Union[str, None] = "46fb64470c0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_digest", sa.String(length=64), nullable=True),
        sa.Column("encrypted_profile", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_members_email_digest"), ["email_digest"], unique=True)
        batch_op.create_index(batch_op.f("ix_members_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_members_status"))
        batch_op.drop_index(batch_op.f("ix_members_email_digest"))
    op.drop_table("members")
