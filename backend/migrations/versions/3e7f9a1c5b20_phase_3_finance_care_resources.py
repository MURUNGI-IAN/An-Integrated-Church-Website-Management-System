"""Add Phase 3 finance, care, resources, documents and certificates.

Revision ID: 3e7f9a1c5b20
Revises: 8c1f6a4d3e20
Create Date: 2026-10-15 13:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3e7f9a1c5b20"
down_revision: Union[str, None] = "8c1f6a4d3e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finance_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=16), nullable=False),
        sa.Column("amount_ugx", sa.Integer(), nullable=False),
        sa.Column("fund", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("entry_type", "fund", "category", "entry_date", "status"):
        op.create_index(f"ix_finance_entries_{column}", "finance_entries", [column], unique=False)

    op.create_table(
        "finance_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fund", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("amount_ugx", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund", "category", "period_start", "period_end", name="uq_finance_budget_period"),
    )
    for column in ("fund", "category", "period_start", "period_end"):
        op.create_index(f"ix_finance_budgets_{column}", "finance_budgets", [column], unique=False)

    op.create_table(
        "finance_pledges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign", sa.String(length=160), nullable=False),
        sa.Column("amount_ugx", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("recorded_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finance_pledges_campaign", "finance_pledges", ["campaign"], unique=False)
    op.create_index("ix_finance_pledges_status", "finance_pledges", ["status"], unique=False)

    op.create_table(
        "pastoral_care_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("care_type", sa.String(length=48), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("member_id", "care_type", "priority", "due_date", "status"):
        op.create_index(f"ix_pastoral_care_tasks_{column}", "pastoral_care_tasks", [column], unique=False)

    op.create_table(
        "church_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_church_resources_is_active", "church_resources", ["is_active"], unique=False)

    op.create_table(
        "resource_bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requested_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["church_resources.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("resource_id", "starts_at", "ends_at", "status"):
        op.create_index(f"ix_resource_bookings_{column}", "resource_bookings", [column], unique=False)

    op.create_table(
        "staff_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=48), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_documents_document_type", "staff_documents", ["document_type"], unique=False)

    op.create_table(
        "member_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("certificate_type", sa.String(length=80), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("certificate_number", sa.String(length=80), nullable=False),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issued_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("certificate_number"),
    )
    for column in ("member_id", "certificate_type", "issued_on"):
        op.create_index(f"ix_member_certificates_{column}", "member_certificates", [column], unique=False)


def downgrade() -> None:
    for table in ("member_certificates", "staff_documents", "resource_bookings", "church_resources",
                  "pastoral_care_tasks", "finance_pledges", "finance_budgets", "finance_entries"):
        op.drop_table(table)
