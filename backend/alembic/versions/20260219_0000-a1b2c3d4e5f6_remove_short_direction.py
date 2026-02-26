"""remove_short_direction

Revision ID: a1b2c3d4e5f6
Revises: f364d831b617
Create Date: 2026-02-19 00:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f364d831b617'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove SHORT direction — system is LONG-only.

    - Convert any existing SHORT recommendations to NO_SETUP
    - Drop short_count column from live20_runs
    - Update CHECK constraint on recommendations to remove 'SHORT'
    """
    # 1. Convert existing SHORT recommendations to NO_SETUP
    op.execute("""
        UPDATE recommendations
        SET recommendation = 'NO_SETUP',
            live20_direction = 'NO_SETUP'
        WHERE live20_direction = 'SHORT'
    """)

    # 2. Drop short_count column from live20_runs
    op.drop_column('live20_runs', 'short_count')

    # 3. Update CHECK constraint to remove SHORT
    op.drop_constraint('ck_recommendations_valid_decision', 'recommendations')
    op.create_check_constraint(
        'ck_recommendations_valid_decision',
        'recommendations',
        "recommendation IN ('Buy', 'Watchlist', 'Not Buy', 'LONG', 'NO_SETUP')",
    )


def downgrade() -> None:
    """Restore SHORT direction support.

    - Restore CHECK constraint with SHORT included
    - Re-add short_count column to live20_runs
    Note: converted SHORT rows remain as NO_SETUP and are not restored.
    """
    # Restore CHECK constraint with SHORT
    op.drop_constraint('ck_recommendations_valid_decision', 'recommendations')
    op.create_check_constraint(
        'ck_recommendations_valid_decision',
        'recommendations',
        "recommendation IN ('Buy', 'Watchlist', 'Not Buy', 'LONG', 'SHORT', 'NO_SETUP')",
    )

    # Re-add short_count column
    op.add_column(
        'live20_runs',
        sa.Column('short_count', sa.Integer(), nullable=False, server_default='0'),
    )
