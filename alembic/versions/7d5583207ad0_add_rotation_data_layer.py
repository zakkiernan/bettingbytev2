"""add rotation data layer

Revision ID: 7d5583207ad0
Revises: 47555eda0919
Create Date: 2026-03-09 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7d5583207ad0'
down_revision: Union[str, Sequence[str], None] = '47555eda0919'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'team_rotation_games',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('team_abbreviation', sa.String(), nullable=True),
        sa.Column('team_name', sa.String(), nullable=True),
        sa.Column('rotation_player_count', sa.Integer(), nullable=True),
        sa.Column('starter_count', sa.Integer(), nullable=True),
        sa.Column('closing_count', sa.Integer(), nullable=True),
        sa.Column('total_stints', sa.Integer(), nullable=True),
        sa.Column('max_out_time_real', sa.Float(), nullable=True),
        sa.Column('total_shift_duration_real', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'team_id', name='uq_team_rotation_game'),
    )
    with op.batch_alter_table('team_rotation_games', schema=None) as batch_op:
        batch_op.create_index('ix_team_rotation_game_lookup', ['game_id', 'team_id'], unique=False)

    op.create_table(
        'player_rotation_games',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('team_abbreviation', sa.String(), nullable=True),
        sa.Column('team_name', sa.String(), nullable=True),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('player_name', sa.String(), nullable=False),
        sa.Column('started', sa.Boolean(), nullable=True),
        sa.Column('played_opening_stint', sa.Boolean(), nullable=True),
        sa.Column('closed_game', sa.Boolean(), nullable=True),
        sa.Column('stint_count', sa.Integer(), nullable=True),
        sa.Column('first_in_time_real', sa.Float(), nullable=True),
        sa.Column('last_out_time_real', sa.Float(), nullable=True),
        sa.Column('total_shift_duration_real', sa.Float(), nullable=True),
        sa.Column('avg_shift_duration_real', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'player_id', name='uq_player_rotation_game'),
    )
    with op.batch_alter_table('player_rotation_games', schema=None) as batch_op:
        batch_op.create_index('ix_player_rotation_game_lookup', ['game_id', 'player_id'], unique=False)
        batch_op.create_index('ix_player_rotation_game_team', ['team_id', 'game_id'], unique=False)

    op.create_table(
        'player_rotation_stints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('team_abbreviation', sa.String(), nullable=True),
        sa.Column('team_name', sa.String(), nullable=True),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('player_name', sa.String(), nullable=False),
        sa.Column('stint_number', sa.Integer(), nullable=False),
        sa.Column('in_time_real', sa.Float(), nullable=True),
        sa.Column('out_time_real', sa.Float(), nullable=True),
        sa.Column('shift_duration_real', sa.Float(), nullable=True),
        sa.Column('player_points', sa.Float(), nullable=True),
        sa.Column('point_differential', sa.Float(), nullable=True),
        sa.Column('usage_percentage', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'player_id', 'stint_number', name='uq_player_rotation_stint'),
    )
    with op.batch_alter_table('player_rotation_stints', schema=None) as batch_op:
        batch_op.create_index('ix_player_rotation_stint_lookup', ['game_id', 'player_id', 'stint_number'], unique=False)
        batch_op.create_index('ix_player_rotation_stint_team', ['team_id', 'game_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('player_rotation_stints', schema=None) as batch_op:
        batch_op.drop_index('ix_player_rotation_stint_team')
        batch_op.drop_index('ix_player_rotation_stint_lookup')
    op.drop_table('player_rotation_stints')

    with op.batch_alter_table('player_rotation_games', schema=None) as batch_op:
        batch_op.drop_index('ix_player_rotation_game_team')
        batch_op.drop_index('ix_player_rotation_game_lookup')
    op.drop_table('player_rotation_games')

    with op.batch_alter_table('team_rotation_games', schema=None) as batch_op:
        batch_op.drop_index('ix_team_rotation_game_lookup')
    op.drop_table('team_rotation_games')
