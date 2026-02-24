"""merge_arena_group_id_branch

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0, c3d4e5f6a7b8
Create Date: 2026-02-24 00:00:00.000000

Trading Analyst Database Migration
Merge migration: joins the arena_group_id branch with the main migration chain.
The group_id column was already applied to the database; this merge simply
reconciles the two heads so alembic upgrade head works correctly.
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = ("e5f6a7b8c9d0", "c3d4e5f6a7b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op merge: group_id column was already applied."""
    pass


def downgrade() -> None:
    """No-op merge downgrade."""
    pass
