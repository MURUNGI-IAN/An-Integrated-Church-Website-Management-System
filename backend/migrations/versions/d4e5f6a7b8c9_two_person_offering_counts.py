"""Add dual-witness offering counts.

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f0a1b2
Create Date: 2026-10-15 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offering_count_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("fund", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("amount_counted_ugx", sa.Integer(), nullable=False),
        sa.Column("verified_amount_ugx", sa.Integer(), nullable=True),
        sa.Column("final_amount_ugx", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("counted_by_id", sa.Integer(), nullable=False),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("finance_entry_id", sa.Integer(), nullable=True),
        sa.Column("encrypted_details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["counted_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["finance_entry_id"], ["finance_entries.id"]),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["verified_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finance_entry_id", name="uq_offering_count_finance_entry"),
    )
    for column in ("service_date", "fund", "status"):
        op.create_index(f"ix_offering_count_batches_{column}", "offering_count_batches", [column], unique=False)


def downgrade() -> None:
    op.drop_table("offering_count_batches")
