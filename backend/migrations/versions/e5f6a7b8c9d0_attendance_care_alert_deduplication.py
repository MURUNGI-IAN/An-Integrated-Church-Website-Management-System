"""Deduplicate automatic care alerts by missed Sunday window.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-15 14:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pastoral_care_tasks") as batch_op:
        batch_op.add_column(sa.Column("attendance_alert_key", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_pastoral_attendance_alert",
            ["member_id", "care_type", "attendance_alert_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("pastoral_care_tasks") as batch_op:
        batch_op.drop_constraint("uq_pastoral_attendance_alert", type_="unique")
        batch_op.drop_column("attendance_alert_key")
