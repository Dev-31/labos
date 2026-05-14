"""add destroy retry tracking to labs

Revision ID: 20260514_0007
Revises: 20260514_0006
Create Date: 2026-05-14 20:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260514_0007"
down_revision = "20260514_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("labs") as batch_op:
        batch_op.add_column(
            sa.Column("destroy_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("last_destroy_error", sa.Text(), nullable=True))

    with op.batch_alter_table("labs") as batch_op:
        batch_op.alter_column("destroy_attempts", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("labs") as batch_op:
        batch_op.drop_column("last_destroy_error")
        batch_op.drop_column("destroy_attempts")
