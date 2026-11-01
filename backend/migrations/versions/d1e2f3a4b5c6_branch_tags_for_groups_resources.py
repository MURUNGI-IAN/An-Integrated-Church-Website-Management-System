"""Add optional branch assignment to groups and resources.

Revision ID: d1e2f3a4b5c6
Revises: b8c9d0e1f2a3
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table_name in ("small_groups", "church_resources"):
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
    for table_name in ("church_resources", "small_groups"):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_branch_id_branches", type_="foreignkey")
            batch_op.drop_index(f"ix_{table_name}_branch_id")
            batch_op.drop_column("branch_id")