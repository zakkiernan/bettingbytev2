"""add role replacement fields to pregame context snapshots

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-03-14 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pregame_context_snapshots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role_replacement_minutes_proxy", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("role_replacement_usage_proxy", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("role_replacement_touches_proxy", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("role_replacement_passes_proxy", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pregame_context_snapshots", schema=None) as batch_op:
        batch_op.drop_column("role_replacement_passes_proxy")
        batch_op.drop_column("role_replacement_touches_proxy")
        batch_op.drop_column("role_replacement_usage_proxy")
        batch_op.drop_column("role_replacement_minutes_proxy")
