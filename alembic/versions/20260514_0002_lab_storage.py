"""add managed lab storage metadata

Revision ID: 20260514_0002
Revises: 20260513_0001
Create Date: 2026-05-14 02:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260514_0002"
down_revision = "20260513_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_storage",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("lab_id", sa.String(length=64), nullable=False),
        sa.Column("persistence_mode", sa.String(length=32), nullable=False),
        sa.Column("root_path", sa.String(length=512), nullable=False),
        sa.Column("workspace_path", sa.String(length=512), nullable=False),
        sa.Column("exports_path", sa.String(length=512), nullable=False),
        sa.Column("quarantine_path", sa.String(length=512), nullable=False),
        sa.Column("snapshots_path", sa.String(length=512), nullable=False),
        sa.Column("workspace_mount_target", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lab_id"),
    )


def downgrade() -> None:
    op.drop_table("lab_storage")
