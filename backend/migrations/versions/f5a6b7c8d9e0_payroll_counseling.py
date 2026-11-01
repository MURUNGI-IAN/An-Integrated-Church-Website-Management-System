"""Add payroll and counseling appointment records.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payroll_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("salary_ugx", sa.Integer(), nullable=False),
        sa.Column("allowances_ugx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deductions_ugx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paye_ugx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nssf_ugx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_ugx", sa.Integer(), nullable=False),
        sa.Column("net_ugx", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "period_start", "period_end", name="uq_payroll_member_period"),
    )
    op.create_index("ix_payroll_records_member_id", "payroll_records", ["member_id"])
    op.create_index("ix_payroll_records_period_start", "payroll_records", ["period_start"])
    op.create_index("ix_payroll_records_period_end", "payroll_records", ["period_end"])

    op.create_table(
        "counseling_appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("counselee_id", sa.Integer(), nullable=False),
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("appointment_type", sa.String(length=24), nullable=False),
        sa.Column("assigned_counselor_id", sa.Integer(), nullable=False),
        sa.Column("assigned_counselor_role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="booked"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_counselor_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["counselee_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_counseling_appointments_counselee_id", "counseling_appointments", ["counselee_id"])
    op.create_index("ix_counseling_appointments_appointment_at", "counseling_appointments", ["appointment_at"])
    op.create_index("ix_counseling_appointments_appointment_type", "counseling_appointments", ["appointment_type"])
    op.create_index("ix_counseling_appointments_assigned_counselor_id", "counseling_appointments", ["assigned_counselor_id"])
    op.create_index("ix_counseling_appointments_status", "counseling_appointments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_counseling_appointments_status", table_name="counseling_appointments")
    op.drop_index("ix_counseling_appointments_assigned_counselor_id", table_name="counseling_appointments")
    op.drop_index("ix_counseling_appointments_appointment_type", table_name="counseling_appointments")
    op.drop_index("ix_counseling_appointments_appointment_at", table_name="counseling_appointments")
    op.drop_index("ix_counseling_appointments_counselee_id", table_name="counseling_appointments")
    op.drop_table("counseling_appointments")
    op.drop_index("ix_payroll_records_period_end", table_name="payroll_records")
    op.drop_index("ix_payroll_records_period_start", table_name="payroll_records")
    op.drop_index("ix_payroll_records_member_id", table_name="payroll_records")
    op.drop_table("payroll_records")
