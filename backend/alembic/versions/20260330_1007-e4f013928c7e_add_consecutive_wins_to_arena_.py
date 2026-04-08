"""add_consecutive_wins_to_arena_simulations

Revision ID: e4f013928c7e
Revises: 0a7455c082f5
Create Date: 2026-03-30 10:07:48.166387

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f013928c7e'
down_revision: Union[str, Sequence[str], None] = '0a7455c082f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add consecutive_wins column to arena_simulations for win-streak-based risk scaling."""
    op.add_column(
        'arena_simulations',
        sa.Column('consecutive_wins', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Remove consecutive_wins column from arena_simulations."""
    op.drop_column('arena_simulations', 'consecutive_wins')
