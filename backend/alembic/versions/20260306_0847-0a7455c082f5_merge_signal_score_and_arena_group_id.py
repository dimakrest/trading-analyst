"""merge_signal_score_and_arena_group_id

Revision ID: 0a7455c082f5
Revises: c3d4e5f6a1b2, c3d4e5f6a7b8
Create Date: 2026-03-06 08:47:35.178626

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a7455c082f5'
down_revision: Union[str, Sequence[str], None] = ('c3d4e5f6a1b2', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade database schema.

    This function applies the migration changes to move
    the database schema forward to this revision.
    """
    pass


def downgrade() -> None:
    """
    Downgrade database schema.

    This function reverses the migration changes to move
    the database schema back to the previous revision.
    """
    pass
