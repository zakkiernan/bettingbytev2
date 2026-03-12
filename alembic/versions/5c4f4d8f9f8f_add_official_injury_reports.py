"""add official injury reports

Revision ID: 5c4f4d8f9f8f
Revises: 1f5d5a1f4c4e
Create Date: 2026-03-11 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5c4f4d8f9f8f"
down_revision: Union[str, Sequence[str], None] = "1f5d5a1f4c4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "official_injury_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("report_time_et", sa.String(), nullable=True),
        sa.Column("report_datetime_utc", sa.DateTime(), nullable=True),
        sa.Column("pdf_url", sa.String(), nullable=False),
        sa.Column("pdf_sha256", sa.String(), nullable=True),
        sa.Column("game_count", sa.Integer(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pdf_url", name="uq_official_injury_report_pdf_url"),
    )
    with op.batch_alter_table("official_injury_reports", schema=None) as batch_op:
        batch_op.create_index("ix_official_injury_report_date", ["report_date"], unique=False)
        batch_op.create_index("ix_official_injury_report_datetime", ["report_datetime_utc"], unique=False)

    op.create_table(
        "official_injury_report_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(), nullable=True),
        sa.Column("report_datetime_utc", sa.DateTime(), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("game_time_et", sa.String(), nullable=True),
        sa.Column("matchup", sa.String(), nullable=True),
        sa.Column("team_id", sa.String(), nullable=True),
        sa.Column("team_abbreviation", sa.String(), nullable=True),
        sa.Column("team_name", sa.String(), nullable=True),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("player_name", sa.String(), nullable=True),
        sa.Column("current_status", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("report_submitted", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["official_injury_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("official_injury_report_entries", schema=None) as batch_op:
        batch_op.create_index("ix_official_injury_report_entries_game_date", ["game_date"], unique=False)
        batch_op.create_index("ix_official_injury_report_entries_player_id", ["player_id"], unique=False)
        batch_op.create_index("ix_official_injury_report_entries_report_datetime_utc", ["report_datetime_utc"], unique=False)
        batch_op.create_index("ix_official_injury_report_entries_report_id", ["report_id"], unique=False)
        batch_op.create_index("ix_official_injury_report_entries_team_abbreviation", ["team_abbreviation"], unique=False)
        batch_op.create_index("ix_official_injury_report_entries_team_id", ["team_id"], unique=False)
        batch_op.create_index("ix_official_injury_report_entry_player", ["player_id", "report_datetime_utc"], unique=False)
        batch_op.create_index("ix_official_injury_report_entry_report", ["report_id", "team_abbreviation"], unique=False)
        batch_op.create_index("ix_official_injury_report_entry_team_date", ["team_abbreviation", "game_date", "report_datetime_utc"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("official_injury_report_entries", schema=None) as batch_op:
        batch_op.drop_index("ix_official_injury_report_entry_team_date")
        batch_op.drop_index("ix_official_injury_report_entry_report")
        batch_op.drop_index("ix_official_injury_report_entry_player")
        batch_op.drop_index("ix_official_injury_report_entries_team_id")
        batch_op.drop_index("ix_official_injury_report_entries_team_abbreviation")
        batch_op.drop_index("ix_official_injury_report_entries_report_id")
        batch_op.drop_index("ix_official_injury_report_entries_report_datetime_utc")
        batch_op.drop_index("ix_official_injury_report_entries_player_id")
        batch_op.drop_index("ix_official_injury_report_entries_game_date")
    op.drop_table("official_injury_report_entries")

    with op.batch_alter_table("official_injury_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_official_injury_report_datetime")
        batch_op.drop_index("ix_official_injury_report_date")
    op.drop_table("official_injury_reports")
