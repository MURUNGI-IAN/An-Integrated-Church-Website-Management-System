"""Add encrypted volunteer-vetting records.

Revision ID: b6c7d8e9f0a1
Revises: a4b5c6d7e8f9
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "volunteer_vetting_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("background_check_status", sa.String(length=16), nullable=False),
        sa.Column("references_checked", sa.Boolean(), nullable=False),
        sa.Column("training_completed_at", sa.Date(), nullable=True),
        sa.Column("service_started_at", sa.Date(), nullable=False),
        sa.Column("service_ended_at", sa.Date(), nullable=True),
        sa.Column("retention_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_volunteer_vetting_records_member_id", "volunteer_vetting_records", ["member_id"])
    op.create_index("ix_volunteer_vetting_records_background_check_status", "volunteer_vetting_records", ["background_check_status"])
    op.create_index("ix_volunteer_vetting_records_retention_until", "volunteer_vetting_records", ["retention_until"])
    op.create_index("ix_volunteer_vetting_records_status", "volunteer_vetting_records", ["status"])


def downgrade() -> None:
    op.drop_index("ix_volunteer_vetting_records_status", table_name="volunteer_vetting_records")
    op.drop_index("ix_volunteer_vetting_records_retention_until", table_name="volunteer_vetting_records")
    op.drop_index("ix_volunteer_vetting_records_background_check_status", table_name="volunteer_vetting_records")
    op.drop_index("ix_volunteer_vetting_records_member_id", table_name="volunteer_vetting_records")
    op.drop_table("volunteer_vetting_records")