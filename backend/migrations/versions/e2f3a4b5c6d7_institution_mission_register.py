"""Add an internal register for institutions and mission fields.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institution_mission_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institution_mission_records_record_type", "institution_mission_records", ["record_type"])
    op.create_index("ix_institution_mission_records_name", "institution_mission_records", ["name"])
    op.create_index("ix_institution_mission_records_is_active", "institution_mission_records", ["is_active"])
    op.create_index("ix_institution_mission_records_branch_id", "institution_mission_records", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_institution_mission_records_branch_id", table_name="institution_mission_records")
    op.drop_index("ix_institution_mission_records_is_active", table_name="institution_mission_records")
    op.drop_index("ix_institution_mission_records_name", table_name="institution_mission_records")
    op.drop_index("ix_institution_mission_records_record_type", table_name="institution_mission_records")
    op.drop_table("institution_mission_records")