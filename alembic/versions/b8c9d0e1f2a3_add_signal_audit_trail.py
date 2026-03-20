"""add signal audit trail

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-18 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_audit_trail",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.Column("stat_type", sa.String(), nullable=False),
        sa.Column("snapshot_phase", sa.String(), nullable=False, server_default="current"),
        sa.Column("line", sa.Float(), nullable=False),
        sa.Column("projected_value", sa.Float(), nullable=False),
        sa.Column("edge", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommended_side", sa.String(), nullable=True),
        sa.Column("readiness_status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("blockers_json", sa.Text(), nullable=True),
        sa.Column("warnings_json", sa.Text(), nullable=True),
        sa.Column("breakdown_json", sa.Text(), nullable=False),
        sa.Column("source_context_captured_at", sa.DateTime(), nullable=True),
        sa.Column("source_injury_report_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_signal_audit_trail_game_captured",
        "signal_audit_trail",
        ["game_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_signal_audit_trail_player_captured",
        "signal_audit_trail",
        ["player_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_signal_audit_trail_phase_captured",
        "signal_audit_trail",
        ["snapshot_phase", "captured_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signal_audit_trail_game_id"),
        "signal_audit_trail",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signal_audit_trail_player_id"),
        "signal_audit_trail",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signal_audit_trail_captured_at"),
        "signal_audit_trail",
        ["captured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_signal_audit_trail_captured_at"), table_name="signal_audit_trail")
    op.drop_index(op.f("ix_signal_audit_trail_player_id"), table_name="signal_audit_trail")
    op.drop_index(op.f("ix_signal_audit_trail_game_id"), table_name="signal_audit_trail")
    op.drop_index("ix_signal_audit_trail_phase_captured", table_name="signal_audit_trail")
    op.drop_index("ix_signal_audit_trail_player_captured", table_name="signal_audit_trail")
    op.drop_index("ix_signal_audit_trail_game_captured", table_name="signal_audit_trail")
    op.drop_table("signal_audit_trail")
