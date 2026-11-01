"""Add language translations and sermon captions.

Revision ID: e4f5a6b7c8d9
Revises: c8d9e0f1a2b3
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_translations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="human"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", "field", "language", name="uq_content_translation_target"),
    )
    op.create_index("ix_content_translations_entity_id", "content_translations", ["entity_id"])
    op.create_index("ix_content_translations_entity_type", "content_translations", ["entity_type"])
    op.create_index("ix_content_translations_language", "content_translations", ["language"])
    op.create_index("ix_content_translations_status", "content_translations", ["status"])

    op.create_table(
        "sermon_captions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sermon_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("file_format", sa.String(length=8), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="human"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["sermon_id"], ["sermons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sermon_id", "language", name="uq_sermon_caption_language"),
    )
    op.create_index("ix_sermon_captions_language", "sermon_captions", ["language"])
    op.create_index("ix_sermon_captions_sermon_id", "sermon_captions", ["sermon_id"])
    op.create_index("ix_sermon_captions_status", "sermon_captions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sermon_captions_status", table_name="sermon_captions")
    op.drop_index("ix_sermon_captions_sermon_id", table_name="sermon_captions")
    op.drop_index("ix_sermon_captions_language", table_name="sermon_captions")
    op.drop_table("sermon_captions")
    op.drop_index("ix_content_translations_status", table_name="content_translations")
    op.drop_index("ix_content_translations_language", table_name="content_translations")
    op.drop_index("ix_content_translations_entity_type", table_name="content_translations")
    op.drop_index("ix_content_translations_entity_id", table_name="content_translations")
    op.drop_table("content_translations")
