"""add_live20_sector_etf_column

Revision ID: 82c52512ae0b
Revises: bd3dfc84f61f
Create Date: 2026-02-11 08:04:12.905729

Trading Analyst Database Migration
Add sector_etf column to recommendations table for Live20 pipeline integration.
This allows Live20 results to display the sector ETF for each stock.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82c52512ae0b'
down_revision: Union[str, Sequence[str], None] = 'bd3dfc84f61f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add live20_sector_etf column to recommendations table."""
    op.add_column(
        "recommendations",
        sa.Column("live20_sector_etf", sa.String(10), nullable=True)
    )


def downgrade() -> None:
    """Remove live20_sector_etf column from recommendations table."""
    op.drop_column("recommendations", "live20_sector_etf")
