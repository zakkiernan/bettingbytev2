"""add pregame context snapshots

Revision ID: 8f3c9c4d2a1b
Revises: 5c4f4d8f9f8f
Create Date: 2026-03-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f3c9c4d2a1b"
down_revision: Union[str, Sequence[str], None] = "5c4f4d8f9f8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pregame_context_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=True),
        sa.Column("team_abbreviation", sa.String(), nullable=True),
        sa.Column("opponent_team_id", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("player_key", sa.String(), nullable=False),
        sa.Column("normalized_player_name", sa.String(), nullable=True),
        sa.Column("player_name", sa.String(), nullable=True),
        sa.Column("expected_start", sa.Boolean(), nullable=True),
        sa.Column("starter_confidence", sa.Float(), nullable=True),
        sa.Column("official_available", sa.Boolean(), nullable=True),
        sa.Column("projected_available", sa.Boolean(), nullable=True),
        sa.Column("late_scratch_risk", sa.Float(), nullable=True),
        sa.Column("teammate_out_count_top7", sa.Float(), nullable=True),
        sa.Column("teammate_out_count_top9", sa.Float(), nullable=True),
        sa.Column("missing_high_usage_teammates", sa.Float(), nullable=True),
        sa.Column("missing_primary_ballhandler", sa.Boolean(), nullable=True),
        sa.Column("missing_frontcourt_rotation_piece", sa.Boolean(), nullable=True),
        sa.Column("vacated_minutes_proxy", sa.Float(), nullable=True),
        sa.Column("vacated_usage_proxy", sa.Float(), nullable=True),
        sa.Column("projected_lineup_confirmed", sa.Boolean(), nullable=True),
        sa.Column("official_starter_flag", sa.Boolean(), nullable=True),
        sa.Column("pregame_context_confidence", sa.Float(), nullable=True),
        sa.Column("source_captured_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "player_key", "captured_at", name="uq_pregame_context_snapshot_capture"),
    )
    with op.batch_alter_table("pregame_context_snapshots", schema=None) as batch_op:
        batch_op.create_index("ix_pregame_context_snapshots_captured_at", ["captured_at"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_game_id", ["game_id"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_normalized_player_name", ["normalized_player_name"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_opponent_team_id", ["opponent_team_id"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_player_id", ["player_id"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_source_captured_at", ["source_captured_at"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_team_abbreviation", ["team_abbreviation"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshots_team_id", ["team_id"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshot_game_capture", ["game_id", "captured_at"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshot_name_lookup", ["game_id", "team_abbreviation", "normalized_player_name", "captured_at"], unique=False)
        batch_op.create_index("ix_pregame_context_snapshot_player_lookup", ["game_id", "team_abbreviation", "player_id", "captured_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("pregame_context_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_pregame_context_snapshot_player_lookup")
        batch_op.drop_index("ix_pregame_context_snapshot_name_lookup")
        batch_op.drop_index("ix_pregame_context_snapshot_game_capture")
        batch_op.drop_index("ix_pregame_context_snapshots_team_id")
        batch_op.drop_index("ix_pregame_context_snapshots_team_abbreviation")
        batch_op.drop_index("ix_pregame_context_snapshots_source_captured_at")
        batch_op.drop_index("ix_pregame_context_snapshots_player_id")
        batch_op.drop_index("ix_pregame_context_snapshots_opponent_team_id")
        batch_op.drop_index("ix_pregame_context_snapshots_normalized_player_name")
        batch_op.drop_index("ix_pregame_context_snapshots_game_id")
        batch_op.drop_index("ix_pregame_context_snapshots_captured_at")
    op.drop_table("pregame_context_snapshots")
