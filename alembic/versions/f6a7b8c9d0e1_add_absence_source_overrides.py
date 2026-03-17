"""add absence source overrides

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-14 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "absence_source_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_abbreviation", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=True),
        sa.Column("player_name", sa.String(), nullable=True),
        sa.Column("normalized_player_name", sa.String(), nullable=True),
        sa.Column("include_as_source", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_absence_source_override_team_date",
        "absence_source_overrides",
        ["team_abbreviation", "start_date", "end_date"],
        unique=False,
    )
    op.create_index(
        "ix_absence_source_override_team_player_id",
        "absence_source_overrides",
        ["team_abbreviation", "player_id"],
        unique=False,
    )
    op.create_index(
        "ix_absence_source_override_team_normalized_name",
        "absence_source_overrides",
        ["team_abbreviation", "normalized_player_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_absence_source_override_team_normalized_name", table_name="absence_source_overrides")
    op.drop_index("ix_absence_source_override_team_player_id", table_name="absence_source_overrides")
    op.drop_index("ix_absence_source_override_team_date", table_name="absence_source_overrides")
    op.drop_table("absence_source_overrides")
