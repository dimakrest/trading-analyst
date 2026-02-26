"""add_name_exchange_to_stock_sectors

Revision ID: 6f11bd8afa20
Revises: 82c52512ae0b
Create Date: 2026-02-11 10:40:33.592853

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f11bd8afa20'
down_revision: Union[str, Sequence[str], None] = '82c52512ae0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add name and exchange columns to stock_sectors for complete caching."""
    op.add_column(
        "stock_sectors",
        sa.Column("name", sa.String(200), nullable=True),
    )
    op.add_column(
        "stock_sectors",
        sa.Column("exchange", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    """Remove name and exchange columns from stock_sectors."""
    op.drop_column("stock_sectors", "exchange")
    op.drop_column("stock_sectors", "name")
