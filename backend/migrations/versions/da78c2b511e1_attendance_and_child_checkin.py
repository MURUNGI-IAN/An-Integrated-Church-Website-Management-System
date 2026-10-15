"""Add member attendance and child check-in

Revision ID: da78c2b511e1
Revises: 9ac7bf120e3d
Create Date: 2026-10-14 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "da78c2b511e1"
down_revision: Union[str, None] = "9ac7bf120e3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("check_in_method", sa.String(length=24), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", "service_name", "service_date", name="uq_member_attendance_service"),
    )
    with op.batch_alter_table("member_attendance", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_member_attendance_member_id"), ["member_id"], unique=False)

    op.create_table(
        "child_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("primary_guardian_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_profile", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["primary_guardian_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("child_profiles", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_child_profiles_is_active"), ["is_active"], unique=False)
        batch_op.create_index(batch_op.f("ix_child_profiles_primary_guardian_id"), ["primary_guardian_id"], unique=False)

    op.create_table(
        "child_pickup_authorizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "member_id", name="uq_child_pickup_member"),
    )
    with op.batch_alter_table("child_pickup_authorizations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_child_pickup_authorizations_child_id"), ["child_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_child_pickup_authorizations_member_id"), ["member_id"], unique=False)

    op.create_table(
        "child_attendance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("child_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=120), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("checked_in_by_member_id", sa.Integer(), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_out_by_member_id", sa.Integer(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["checked_in_by_member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["checked_out_by_member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["child_id"], ["child_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "service_name", "service_date", name="uq_child_attendance_service"),
    )
    with op.batch_alter_table("child_attendance", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_child_attendance_child_id"), ["child_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("child_attendance", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_child_attendance_child_id"))
    op.drop_table("child_attendance")
    with op.batch_alter_table("child_pickup_authorizations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_child_pickup_authorizations_member_id"))
        batch_op.drop_index(batch_op.f("ix_child_pickup_authorizations_child_id"))
    op.drop_table("child_pickup_authorizations")
    with op.batch_alter_table("child_profiles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_child_profiles_primary_guardian_id"))
        batch_op.drop_index(batch_op.f("ix_child_profiles_is_active"))
    op.drop_table("child_profiles")
    with op.batch_alter_table("member_attendance", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_member_attendance_member_id"))
    op.drop_table("member_attendance")
