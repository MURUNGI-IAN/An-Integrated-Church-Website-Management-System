"""Add encrypted governance meeting minutes and resolutions.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-15 14:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "governance_meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encrypted_minutes", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_meetings_meeting_date", "governance_meetings", ["meeting_date"])
    op.create_index("ix_governance_meetings_status", "governance_meetings", ["status"])

    op.create_table(
        "governance_resolutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["governance_meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_governance_resolutions_meeting_id", "governance_resolutions", ["meeting_id"])
    op.create_index("ix_governance_resolutions_status", "governance_resolutions", ["status"])
    op.create_index("ix_governance_resolutions_due_date", "governance_resolutions", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_governance_resolutions_due_date", table_name="governance_resolutions")
    op.drop_index("ix_governance_resolutions_status", table_name="governance_resolutions")
    op.drop_index("ix_governance_resolutions_meeting_id", table_name="governance_resolutions")
    op.drop_table("governance_resolutions")
    op.drop_index("ix_governance_meetings_status", table_name="governance_meetings")
    op.drop_index("ix_governance_meetings_meeting_date", table_name="governance_meetings")
    op.drop_table("governance_meetings")
