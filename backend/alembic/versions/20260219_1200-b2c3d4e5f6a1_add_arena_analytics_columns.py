"""add_arena_analytics_columns

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-02-19 12:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 6 analytics metrics columns to arena_simulations.

    These columns are computed at simulation finalization and provide
    deeper performance analysis: hold duration, win/loss averages,
    profit factor, Sharpe ratio, and total realized P&L.
    """
    op.add_column(
        'arena_simulations',
        sa.Column('avg_hold_days', sa.Numeric(precision=8, scale=2), nullable=True),
    )
    op.add_column(
        'arena_simulations',
        sa.Column('avg_win_pnl', sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        'arena_simulations',
        sa.Column('avg_loss_pnl', sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        'arena_simulations',
        sa.Column('profit_factor', sa.Numeric(precision=8, scale=4), nullable=True),
    )
    op.add_column(
        'arena_simulations',
        sa.Column('sharpe_ratio', sa.Numeric(precision=8, scale=4), nullable=True),
    )
    op.add_column(
        'arena_simulations',
        sa.Column('total_realized_pnl', sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Remove analytics metrics columns from arena_simulations."""
    op.drop_column('arena_simulations', 'total_realized_pnl')
    op.drop_column('arena_simulations', 'sharpe_ratio')
    op.drop_column('arena_simulations', 'profit_factor')
    op.drop_column('arena_simulations', 'avg_loss_pnl')
    op.drop_column('arena_simulations', 'avg_win_pnl')
    op.drop_column('arena_simulations', 'avg_hold_days')
