"""Assign staff accounts to a default branch.

Revision ID: c8d9e0f1a2b3
Revises: b6c7d8e9f0a1
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_admin_users_branch_id", ["branch_id"])
        batch_op.create_foreign_key(
            "fk_admin_users_branch_id_branches",
            "branches",
            ["branch_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.drop_constraint("fk_admin_users_branch_id_branches", type_="foreignkey")
        batch_op.drop_index("ix_admin_users_branch_id")
        batch_op.drop_column("branch_id")