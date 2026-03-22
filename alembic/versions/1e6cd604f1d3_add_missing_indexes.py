"""add missing indexes

Revision ID: 1e6cd604f1d3
Revises: f4a95813c268
Create Date: 2026-03-22 15:35:03.172134

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1e6cd604f1d3"
down_revision: Union[str, Sequence[str], None] = "f4a95813c268"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("absence_impact_summaries", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_absence_impact_summaries_beneficiary_player_id"),
            ["beneficiary_player_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_absence_impact_summaries_source_player_id"),
            ["source_player_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_absence_impact_summaries_team_abbreviation"),
            ["team_abbreviation"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_absence_impact_summaries_window_end_date"),
            ["window_end_date"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_absence_impact_summaries_window_start_date"),
            ["window_start_date"],
            unique=False,
        )

    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_games_game_date"), ["game_date"], unique=False)

    with op.batch_alter_table("odds_snapshots", schema=None) as batch_op:
        batch_op.create_index(
            "ix_odds_snapshot_phase_stat_capture",
            ["market_phase", "stat_type", "captured_at"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_odds_snapshots_market_phase"), ["market_phase"], unique=False)
        batch_op.create_index(batch_op.f("ix_odds_snapshots_stat_type"), ["stat_type"], unique=False)

    with op.batch_alter_table("player_prop_snapshots", schema=None) as batch_op:
        batch_op.create_index(
            "ix_player_prop_snapshot_stat_live_capture",
            ["stat_type", "is_live", "captured_at"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_player_prop_snapshots_stat_type"), ["stat_type"], unique=False)

    with op.batch_alter_table("player_rotation_games", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_player_rotation_games_game_id"), ["game_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rotation_games_player_id"), ["player_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rotation_games_team_id"), ["team_id"], unique=False)

    with op.batch_alter_table("player_rotation_stints", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_player_rotation_stints_game_id"), ["game_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rotation_stints_player_id"), ["player_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_player_rotation_stints_team_id"), ["team_id"], unique=False)

    with op.batch_alter_table("team_rotation_games", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_team_rotation_games_game_id"), ["game_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_team_rotation_games_team_id"), ["team_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("team_rotation_games", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_team_rotation_games_team_id"))
        batch_op.drop_index(batch_op.f("ix_team_rotation_games_game_id"))

    with op.batch_alter_table("player_rotation_stints", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_rotation_stints_team_id"))
        batch_op.drop_index(batch_op.f("ix_player_rotation_stints_player_id"))
        batch_op.drop_index(batch_op.f("ix_player_rotation_stints_game_id"))

    with op.batch_alter_table("player_rotation_games", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_rotation_games_team_id"))
        batch_op.drop_index(batch_op.f("ix_player_rotation_games_player_id"))
        batch_op.drop_index(batch_op.f("ix_player_rotation_games_game_id"))

    with op.batch_alter_table("player_prop_snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_player_prop_snapshots_stat_type"))
        batch_op.drop_index("ix_player_prop_snapshot_stat_live_capture")

    with op.batch_alter_table("odds_snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_odds_snapshots_stat_type"))
        batch_op.drop_index(batch_op.f("ix_odds_snapshots_market_phase"))
        batch_op.drop_index("ix_odds_snapshot_phase_stat_capture")

    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_games_game_date"))

    with op.batch_alter_table("absence_impact_summaries", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_absence_impact_summaries_window_start_date"))
        batch_op.drop_index(batch_op.f("ix_absence_impact_summaries_window_end_date"))
        batch_op.drop_index(batch_op.f("ix_absence_impact_summaries_team_abbreviation"))
        batch_op.drop_index(batch_op.f("ix_absence_impact_summaries_source_player_id"))
        batch_op.drop_index(batch_op.f("ix_absence_impact_summaries_beneficiary_player_id"))
