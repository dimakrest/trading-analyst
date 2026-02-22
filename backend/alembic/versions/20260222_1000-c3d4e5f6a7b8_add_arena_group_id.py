"""add_arena_group_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a1
Create Date: 2026-02-22 10:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add group_id column to arena_simulations for multi-strategy comparisons.

    The group_id is a UUID (stored as String(36)) that links multiple simulations
    created together as part of a comparison run. Nullable because single simulations
    do not belong to any group.
    """
    # Note: no index=True here — the explicit op.create_index below provides
    # the named index referenced in downgrade(). Using both would create duplicates.
    op.add_column(
        'arena_simulations',
        sa.Column('group_id', sa.String(36), nullable=True),
    )
    op.create_index('ix_arena_simulations_group_id', 'arena_simulations', ['group_id'])


def downgrade() -> None:
    """Remove group_id column from arena_simulations."""
    op.drop_index('ix_arena_simulations_group_id', table_name='arena_simulations')
    op.drop_column('arena_simulations', 'group_id')
