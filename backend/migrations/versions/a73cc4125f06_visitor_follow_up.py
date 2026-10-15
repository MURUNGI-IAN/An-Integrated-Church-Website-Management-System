"""Add encrypted visitor follow-up requests.

Revision ID: a73cc4125f06
Revises: c2d4e6f8a103
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a73cc4125f06"
down_revision: Union[str, None] = "c2d4e6f8a103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visitor_visits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("visitor_visits", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_visitor_visits_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("visitor_visits", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_visitor_visits_status"))
    op.drop_table("visitor_visits")