"""Add linked, single-use finance correction entries.

Revision ID: c7d8e9f0a1b2
Revises: a2b3c4d5e6f7
Create Date: 2026-10-15 14:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("finance_entries") as batch_op:
        batch_op.add_column(sa.Column("correction_of_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_finance_entries_correction_of_id_finance_entries",
            "finance_entries",
            ["correction_of_id"],
            ["id"],
        )
        batch_op.create_index("ix_finance_entries_correction_of_id", ["correction_of_id"], unique=False)
        batch_op.create_unique_constraint("uq_finance_entry_correction", ["correction_of_id"])


def downgrade() -> None:
    with op.batch_alter_table("finance_entries") as batch_op:
        batch_op.drop_constraint("uq_finance_entry_correction", type_="unique")
        batch_op.drop_index("ix_finance_entries_correction_of_id")
        batch_op.drop_constraint("fk_finance_entries_correction_of_id_finance_entries", type_="foreignkey")
        batch_op.drop_column("correction_of_id")
