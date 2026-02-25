"""add_bounce_rate_column

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-25 00:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add live20_bounce_rate and live20_bounce_events columns to recommendations.

    live20_bounce_rate stores the historical fraction of MA20 pullback events
    that recovered >=2.5% within 15 days (0.00-1.00). live20_bounce_events
    stores the number of pullback events used to compute the rate.
    Both columns are nullable — historical recommendations will have NULL.
    """
    op.add_column(
        'recommendations',
        sa.Column('live20_bounce_rate', sa.Numeric(3, 2), nullable=True),
    )
    op.add_column(
        'recommendations',
        sa.Column('live20_bounce_events', sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        'ck_bounce_rate_range',
        'recommendations',
        'live20_bounce_rate >= 0 AND live20_bounce_rate <= 1',
    )


def downgrade() -> None:
    """Remove live20_bounce_rate and live20_bounce_events columns from recommendations."""
    op.drop_constraint('ck_bounce_rate_range', 'recommendations', type_='check')
    op.drop_column('recommendations', 'live20_bounce_events')
    op.drop_column('recommendations', 'live20_bounce_rate')
