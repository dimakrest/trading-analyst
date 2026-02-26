"""add_live20_atr_rvol_columns

Revision ID: 777871ff2314
Revises: fbac8711232a
Create Date: 2026-02-10 06:17:20.175751

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '777871ff2314'
down_revision: Union[str, Sequence[str], None] = 'fbac8711232a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade database schema.

    Adds live20_atr and live20_rvol columns to recommendations table.
    - live20_atr: Average True Range (Numeric 12,4) for volatility context
    - live20_rvol: Relative volume ratio (Numeric 8,2) for conviction assessment
    Both columns are nullable for backward compatibility with existing records.
    """
    op.add_column(
        'recommendations',
        sa.Column('live20_atr', sa.Numeric(precision=12, scale=4), nullable=True)
    )
    op.add_column(
        'recommendations',
        sa.Column('live20_rvol', sa.Numeric(precision=8, scale=2), nullable=True)
    )


def downgrade() -> None:
    """
    Downgrade database schema.

    Removes live20_atr and live20_rvol columns from recommendations table.
    """
    op.drop_column('recommendations', 'live20_rvol')
    op.drop_column('recommendations', 'live20_atr')
