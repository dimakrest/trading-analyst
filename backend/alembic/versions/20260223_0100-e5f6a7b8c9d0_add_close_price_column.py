"""add_close_price_column

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-23 01:00:00.000000

Trading Analyst Database Migration
Adds live20_close_price column to recommendations table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add close price column to recommendations."""
    op.add_column(
        "recommendations",
        sa.Column("live20_close_price", sa.Numeric(12, 4), nullable=True),
    )


def downgrade() -> None:
    """Remove close price column from recommendations."""
    op.drop_column("recommendations", "live20_close_price")
