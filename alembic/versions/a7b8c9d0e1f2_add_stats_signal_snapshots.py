"""add stats signal snapshots

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-16 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stats_signal_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("player_name", sa.String(), nullable=False),
        sa.Column("team_abbreviation", sa.String(), nullable=True),
        sa.Column("opponent_abbreviation", sa.String(), nullable=True),
        sa.Column("stat_type", sa.String(), nullable=False),
        sa.Column("snapshot_phase", sa.String(), nullable=False, server_default="current"),
        sa.Column("line", sa.Float(), nullable=False),
        sa.Column("over_odds", sa.Integer(), nullable=False),
        sa.Column("under_odds", sa.Integer(), nullable=False),
        sa.Column("projected_value", sa.Float(), nullable=False),
        sa.Column("edge_over", sa.Float(), nullable=True),
        sa.Column("edge_under", sa.Float(), nullable=True),
        sa.Column("over_probability", sa.Float(), nullable=True),
        sa.Column("under_probability", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("recommended_side", sa.String(), nullable=True),
        sa.Column("recent_hit_rate", sa.Float(), nullable=True),
        sa.Column("recent_games_count", sa.Integer(), nullable=True),
        sa.Column("key_factor", sa.String(), nullable=True),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("readiness_status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("using_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("readiness_json", sa.Text(), nullable=False),
        sa.Column("breakdown_json", sa.Text(), nullable=False),
        sa.Column("opportunity_json", sa.Text(), nullable=False),
        sa.Column("features_json", sa.Text(), nullable=False),
        sa.Column("source_prop_captured_at", sa.DateTime(), nullable=True),
        sa.Column("source_context_captured_at", sa.DateTime(), nullable=True),
        sa.Column("source_injury_report_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stats_signal_snapshot_player_created",
        "stats_signal_snapshots",
        ["player_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stats_signal_snapshot_game_created",
        "stats_signal_snapshots",
        ["game_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stats_signal_snapshot_status_created",
        "stats_signal_snapshots",
        ["readiness_status", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stats_signal_snapshots_game_id"),
        "stats_signal_snapshots",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stats_signal_snapshots_player_id"),
        "stats_signal_snapshots",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stats_signal_snapshots_source_prop_captured_at"),
        "stats_signal_snapshots",
        ["source_prop_captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stats_signal_snapshots_created_at"),
        "stats_signal_snapshots",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stats_signal_snapshots_created_at"), table_name="stats_signal_snapshots")
    op.drop_index(op.f("ix_stats_signal_snapshots_source_prop_captured_at"), table_name="stats_signal_snapshots")
    op.drop_index(op.f("ix_stats_signal_snapshots_player_id"), table_name="stats_signal_snapshots")
    op.drop_index(op.f("ix_stats_signal_snapshots_game_id"), table_name="stats_signal_snapshots")
    op.drop_index("ix_stats_signal_snapshot_status_created", table_name="stats_signal_snapshots")
    op.drop_index("ix_stats_signal_snapshot_game_created", table_name="stats_signal_snapshots")
    op.drop_index("ix_stats_signal_snapshot_player_created", table_name="stats_signal_snapshots")
    op.drop_table("stats_signal_snapshots")
