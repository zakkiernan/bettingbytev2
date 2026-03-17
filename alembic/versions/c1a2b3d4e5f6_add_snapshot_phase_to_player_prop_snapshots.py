"""add snapshot phase to player prop snapshots

Revision ID: c1a2b3d4e5f6
Revises: 8f3c9c4d2a1b
Create Date: 2026-03-13 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8f3c9c4d2a1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("player_prop_snapshots")}

    # Step 1: add the column only if it doesn't already exist.
    if "snapshot_phase" not in columns:
        with op.batch_alter_table("player_prop_snapshots", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("snapshot_phase", sa.String(), nullable=True, server_default="current")
            )

    # Step 2: backfill any rows that are still NULL (or were created during a partial run).
    op.execute("UPDATE player_prop_snapshots SET snapshot_phase = 'current' WHERE snapshot_phase IS NULL")

    # Step 3: flip nullable=False, rebuild constraint and index.
    with op.batch_alter_table("player_prop_snapshots", schema=None) as batch_op:
        batch_op.alter_column("snapshot_phase", existing_type=sa.String(), nullable=False, server_default=None)
        batch_op.drop_constraint("uq_player_prop_snapshot_market", type_="unique")
        batch_op.drop_index("ix_player_prop_snapshot_lookup")
        batch_op.create_unique_constraint(
            "uq_player_prop_snapshot_market_phase",
            ["game_id", "player_id", "stat_type", "is_live", "snapshot_phase"],
        )
        batch_op.create_index(
            "ix_player_prop_snapshot_lookup",
            ["game_id", "player_id", "stat_type", "is_live", "snapshot_phase"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("player_prop_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_player_prop_snapshot_lookup")
        batch_op.drop_constraint("uq_player_prop_snapshot_market_phase", type_="unique")
        batch_op.create_unique_constraint(
            "uq_player_prop_snapshot_market",
            ["game_id", "player_id", "stat_type", "is_live"],
        )
        batch_op.create_index(
            "ix_player_prop_snapshot_lookup",
            ["game_id", "player_id", "stat_type", "is_live"],
            unique=False,
        )
        batch_op.drop_column("snapshot_phase")
