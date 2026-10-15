"""Add small group directory and waitlist.

Revision ID: 8c1f6a4d3e20
Revises: b5a8d2c74e19
Create Date: 2026-10-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c1f6a4d3e20"
down_revision: Union[str, None] = "b5a8d2c74e19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "small_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("meeting_area", sa.String(length=160), nullable=False),
        sa.Column("meeting_day", sa.String(length=16), nullable=False),
        sa.Column("meeting_time", sa.String(length=40), nullable=False),
        sa.Column("age_group", sa.String(length=80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("small_groups", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_small_groups_is_open"), ["is_open"], unique=False)
        batch_op.create_index(batch_op.f("ix_small_groups_is_published"), ["is_published"], unique=False)

    op.create_table(
        "group_waitlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("contact_digest", sa.String(length=64), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["small_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "contact_digest", name="uq_group_waitlist_contact"),
    )
    with op.batch_alter_table("group_waitlist", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_group_waitlist_group_id"), ["group_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_group_waitlist_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("group_waitlist", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_group_waitlist_status"))
        batch_op.drop_index(batch_op.f("ix_group_waitlist_group_id"))
    op.drop_table("group_waitlist")
    with op.batch_alter_table("small_groups", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_small_groups_is_published"))
        batch_op.drop_index(batch_op.f("ix_small_groups_is_open"))
    op.drop_table("small_groups")