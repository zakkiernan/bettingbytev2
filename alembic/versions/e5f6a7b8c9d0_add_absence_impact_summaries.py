"""add absence impact summaries

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-14 01:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "absence_impact_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_player_id", sa.String(), nullable=False),
        sa.Column("source_player_name", sa.String(), nullable=False),
        sa.Column("beneficiary_player_id", sa.String(), nullable=False),
        sa.Column("beneficiary_player_name", sa.String(), nullable=False),
        sa.Column("team_abbreviation", sa.String(), nullable=False),
        sa.Column("window_start_date", sa.Date(), nullable=True),
        sa.Column("window_end_date", sa.Date(), nullable=True),
        sa.Column("source_out_game_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_active_game_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beneficiary_out_game_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beneficiary_active_game_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minutes_delta", sa.Float(), nullable=True),
        sa.Column("points_delta", sa.Float(), nullable=True),
        sa.Column("rebounds_delta", sa.Float(), nullable=True),
        sa.Column("assists_delta", sa.Float(), nullable=True),
        sa.Column("blocks_delta", sa.Float(), nullable=True),
        sa.Column("usage_delta", sa.Float(), nullable=True),
        sa.Column("touches_delta", sa.Float(), nullable=True),
        sa.Column("passes_delta", sa.Float(), nullable=True),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("sample_confidence", sa.Float(), nullable=True),
        sa.Column("build_version", sa.String(), nullable=False, server_default="absence-impact-v1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_player_id",
            "beneficiary_player_id",
            "team_abbreviation",
            "window_start_date",
            "window_end_date",
            name="uq_absence_impact_summary_window",
        ),
    )
    op.create_index(
        "ix_absence_impact_source_lookup",
        "absence_impact_summaries",
        ["source_player_id", "team_abbreviation", "window_end_date"],
        unique=False,
    )
    op.create_index(
        "ix_absence_impact_beneficiary_lookup",
        "absence_impact_summaries",
        ["beneficiary_player_id", "team_abbreviation", "window_end_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_absence_impact_beneficiary_lookup", table_name="absence_impact_summaries")
    op.drop_index("ix_absence_impact_source_lookup", table_name="absence_impact_summaries")
    op.drop_table("absence_impact_summaries")
