"""expand audit event metadata and filters

Revision ID: 20260514_0004
Revises: 20260514_0003
Create Date: 2026-05-14 05:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260514_0004"
down_revision = "20260514_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(
            sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system")
        )
        batch_op.add_column(sa.Column("actor_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("resource_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("resource_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_events_actor_type", ["actor_type"], unique=False)
        batch_op.create_index("ix_events_event_type", ["event_type"], unique=False)
        batch_op.create_index("ix_events_lab_id", ["lab_id"], unique=False)
        batch_op.create_index("ix_events_resource_id", ["resource_id"], unique=False)
        batch_op.create_index("ix_events_resource_type", ["resource_type"], unique=False)
        batch_op.create_index("ix_events_run_id", ["run_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_index("ix_events_run_id")
        batch_op.drop_index("ix_events_resource_type")
        batch_op.drop_index("ix_events_resource_id")
        batch_op.drop_index("ix_events_lab_id")
        batch_op.drop_index("ix_events_event_type")
        batch_op.drop_index("ix_events_actor_type")
        batch_op.drop_column("resource_id")
        batch_op.drop_column("resource_type")
        batch_op.drop_column("actor_id")
        batch_op.drop_column("actor_type")
