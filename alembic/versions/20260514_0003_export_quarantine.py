"""expand export metadata for quarantine workflow

Revision ID: 20260514_0003
Revises: 20260514_0002
Create Date: 2026-05-14 04:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260514_0003"
down_revision = "20260514_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exports") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("state", sa.String(length=32), nullable=False, server_default="quarantined")
        )
        batch_op.add_column(
            sa.Column(
                "quarantine_path",
                sa.String(length=512),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(sa.Column("released_path", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("denial_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("exports") as batch_op:
        batch_op.drop_column("denial_reason")
        batch_op.drop_column("size_bytes")
        batch_op.drop_column("approval_required")
        batch_op.drop_column("released_path")
        batch_op.drop_column("quarantine_path")
        batch_op.drop_column("state")
        batch_op.drop_column("run_id")
