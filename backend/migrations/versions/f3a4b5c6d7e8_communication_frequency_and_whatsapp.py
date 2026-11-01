"""Extend communication preferences for WhatsApp and delivery limits.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("member_communication_consents") as batch_op:
        batch_op.add_column(sa.Column("delivery_frequency", sa.String(length=24), nullable=False, server_default="essential_only"))
        batch_op.add_column(sa.Column("quiet_hours_start", sa.String(length=5), nullable=False, server_default="21:00"))
        batch_op.add_column(sa.Column("quiet_hours_end", sa.String(length=5), nullable=False, server_default="07:00"))
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Kampala"))


def downgrade() -> None:
    with op.batch_alter_table("member_communication_consents") as batch_op:
        batch_op.drop_column("timezone")
        batch_op.drop_column("quiet_hours_end")
        batch_op.drop_column("quiet_hours_start")
        batch_op.drop_column("delivery_frequency")