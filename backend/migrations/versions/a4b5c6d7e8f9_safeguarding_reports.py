"""Add encrypted safeguarding incident and complaint reports.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "safeguarding_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("involves_restricted_staff", sa.Boolean(), nullable=False),
        sa.Column("serious_child_protection", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retention_until", sa.Date(), nullable=False),
        sa.Column("external_referral_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("investigation_started_by_id", sa.Integer(), nullable=True),
        sa.Column("senior_resolution_approval_by_id", sa.Integer(), nullable=True),
        sa.Column("trustee_resolution_approval_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["investigation_started_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["senior_resolution_approval_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["trustee_resolution_approval_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safeguarding_reports_involves_restricted_staff", "safeguarding_reports", ["involves_restricted_staff"])
    op.create_index("ix_safeguarding_reports_serious_child_protection", "safeguarding_reports", ["serious_child_protection"])
    op.create_index("ix_safeguarding_reports_status", "safeguarding_reports", ["status"])
    op.create_index("ix_safeguarding_reports_retention_until", "safeguarding_reports", ["retention_until"])


def downgrade() -> None:
    op.drop_index("ix_safeguarding_reports_retention_until", table_name="safeguarding_reports")
    op.drop_index("ix_safeguarding_reports_status", table_name="safeguarding_reports")
    op.drop_index("ix_safeguarding_reports_serious_child_protection", table_name="safeguarding_reports")
    op.drop_index("ix_safeguarding_reports_involves_restricted_staff", table_name="safeguarding_reports")
    op.drop_table("safeguarding_reports")