"""Add volunteer availability and rota assignments.

Revision ID: f17a0be96231
Revises: e3b7f2a91c45
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f17a0be96231"
down_revision: Union[str, None] = "e3b7f2a91c45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "volunteer_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "service_name", "service_date", name="uq_volunteer_availability_service"),
    )
    with op.batch_alter_table("volunteer_availability", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_volunteer_availability_member_id"), ["member_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_volunteer_availability_service_date"), ["service_date"], unique=False)

    op.create_table(
        "rota_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("role_name", sa.String(length=120), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_name", "service_date", "role_name", name="uq_rota_service_role"),
        sa.UniqueConstraint("member_id", "service_name", "service_date", name="uq_rota_member_service"),
    )
    with op.batch_alter_table("rota_assignments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rota_assignments_member_id"), ["member_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_rota_assignments_service_date"), ["service_date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("rota_assignments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_rota_assignments_service_date"))
        batch_op.drop_index(batch_op.f("ix_rota_assignments_member_id"))
    op.drop_table("rota_assignments")
    with op.batch_alter_table("volunteer_availability", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_volunteer_availability_service_date"))
        batch_op.drop_index(batch_op.f("ix_volunteer_availability_member_id"))
    op.drop_table("volunteer_availability")