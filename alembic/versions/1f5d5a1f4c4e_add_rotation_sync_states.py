"""add rotation sync states

Revision ID: 1f5d5a1f4c4e
Revises: 7d5583207ad0
Create Date: 2026-03-09 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1f5d5a1f4c4e"
down_revision: Union[str, Sequence[str], None] = "7d5583207ad0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rotation_sync_states",
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("season", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(), nullable=True),
        sa.Column("last_succeeded_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_type", sa.String(), nullable=True),
        sa.Column("last_error_text", sa.Text(), nullable=True),
        sa.Column("last_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("game_id"),
    )
    with op.batch_alter_table("rotation_sync_states", schema=None) as batch_op:
        batch_op.create_index("ix_rotation_sync_state_season", ["season"], unique=False)
        batch_op.create_index("ix_rotation_sync_state_season_status", ["season", "status", "next_retry_at"], unique=False)
        batch_op.create_index("ix_rotation_sync_state_status_due", ["status", "next_retry_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("rotation_sync_states", schema=None) as batch_op:
        batch_op.drop_index("ix_rotation_sync_state_status_due")
        batch_op.drop_index("ix_rotation_sync_state_season_status")
        batch_op.drop_index("ix_rotation_sync_state_season")

    op.drop_table("rotation_sync_states")
