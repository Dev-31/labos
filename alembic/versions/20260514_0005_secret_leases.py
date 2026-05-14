"""add secret lease tracking

Revision ID: 20260514_0005
Revises: 20260514_0004
Create Date: 2026-05-14 06:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260514_0005"
down_revision = "20260514_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secret_leases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("lab_id", sa.String(length=64), nullable=False),
        sa.Column("secret_name", sa.String(length=128), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lab_id"], ["labs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_secret_leases_lab_id", "secret_leases", ["lab_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_secret_leases_lab_id", table_name="secret_leases")
    op.drop_table("secret_leases")
