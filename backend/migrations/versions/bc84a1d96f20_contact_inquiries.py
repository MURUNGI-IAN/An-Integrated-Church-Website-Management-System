"""Add encrypted public contact inquiries.

Revision ID: bc84a1d96f20
Revises: da78c2b511e1
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bc84a1d96f20"
down_revision: Union[str, None] = "da78c2b511e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_inquiries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("contact_inquiries", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_contact_inquiries_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("contact_inquiries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contact_inquiries_status"))
    op.drop_table("contact_inquiries")