"""remove_pricing_columns

Revision ID: d26b7940afd7
Revises: 6f11bd8afa20
Create Date: 2026-02-13 08:53:14.335040

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd26b7940afd7'
down_revision: Union[str, Sequence[str], None] = '6f11bd8afa20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove pricing-related columns from recommendations and live20_runs tables.

    Phase 2 of decoupling entry/stop loss from Live20:
    - Remove entry_price, stop_loss, take_profit from recommendations
    - Remove live20_entry_strategy, live20_exit_strategy from recommendations
    - Remove strategy_config from live20_runs
    """
    # Remove pricing columns from recommendations table
    op.drop_column('recommendations', 'entry_price')
    op.drop_column('recommendations', 'stop_loss')
    op.drop_column('recommendations', 'take_profit')
    op.drop_column('recommendations', 'live20_entry_strategy')
    op.drop_column('recommendations', 'live20_exit_strategy')

    # Remove strategy_config from live20_runs table
    op.drop_column('live20_runs', 'strategy_config')


def downgrade() -> None:
    """Recreate pricing-related columns as nullable for rollback support."""
    # Recreate pricing columns in recommendations table (nullable)
    op.add_column(
        'recommendations',
        sa.Column('entry_price', sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        'recommendations',
        sa.Column('stop_loss', sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        'recommendations',
        sa.Column('take_profit', sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        'recommendations',
        sa.Column('live20_entry_strategy', sa.String(20), nullable=True),
    )
    op.add_column(
        'recommendations',
        sa.Column('live20_exit_strategy', sa.String(20), nullable=True),
    )

    # Recreate strategy_config in live20_runs table (nullable)
    op.add_column(
        'live20_runs',
        sa.Column('strategy_config', sa.JSON(), nullable=True),
    )
