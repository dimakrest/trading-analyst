"""add_scoring_algorithm_columns

Revision ID: 0f07a028150e
Revises: d26b7940afd7
Create Date: 2026-02-16 09:10:23.074826

Trading Analyst Database Migration
Add scoring algorithm columns to recommendations and live20_runs tables to support
pluggable scoring algorithms (CCI and RSI-2). This enables the Live20 system to use
different momentum indicators based on configuration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f07a028150e'
down_revision: Union[str, Sequence[str], None] = 'd26b7940afd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scoring algorithm columns to recommendations and live20_runs tables.

    Adds to recommendations table:
    - live20_scoring_algorithm: Which algorithm was used ('cci' or 'rsi2')
    - live20_rsi2_value: RSI-2 indicator value (0-100)
    - live20_rsi2_score: RSI-2 graduated score (0, 5, 10, 15, or 20)

    Adds to live20_runs table:
    - scoring_algorithm: Which algorithm was used for this run
    """
    # recommendations table
    op.add_column('recommendations', sa.Column(
        'live20_scoring_algorithm', sa.String(20), nullable=True, server_default='cci'
    ))
    op.add_column('recommendations', sa.Column(
        'live20_rsi2_value', sa.Numeric(8, 2), nullable=True
    ))
    op.add_column('recommendations', sa.Column(
        'live20_rsi2_score', sa.Integer, nullable=True
    ))

    # live20_runs table
    op.add_column('live20_runs', sa.Column(
        'scoring_algorithm', sa.String(20), nullable=True, server_default='cci'
    ))


def downgrade() -> None:
    """Remove scoring algorithm columns from recommendations and live20_runs tables."""
    # live20_runs table
    op.drop_column('live20_runs', 'scoring_algorithm')

    # recommendations table (reverse order of creation)
    op.drop_column('recommendations', 'live20_rsi2_score')
    op.drop_column('recommendations', 'live20_rsi2_value')
    op.drop_column('recommendations', 'live20_scoring_algorithm')
