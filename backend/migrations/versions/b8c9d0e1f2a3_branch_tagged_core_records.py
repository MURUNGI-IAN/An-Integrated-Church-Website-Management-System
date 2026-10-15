"""Add optional branch assignment to core operational records.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-15 15:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BRANCHED_TABLES = (
    "members",
    "member_attendance",
    "events",
    "finance_entries",
    "finance_budgets",
    "finance_pledges",
    "offering_count_batches",
    "governance_meetings",
)


def upgrade() -> None:
    for table_name in BRANCHED_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
            batch_op.create_index(f"ix_{table_name}_branch_id", ["branch_id"])
            batch_op.create_foreign_key(
                f"fk_{table_name}_branch_id_branches",
                "branches",
                ["branch_id"],
                ["id"],
            )


def downgrade() -> None:
    for table_name in reversed(BRANCHED_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_branch_id_branches", type_="foreignkey")
            batch_op.drop_index(f"ix_{table_name}_branch_id")
            batch_op.drop_column("branch_id")
