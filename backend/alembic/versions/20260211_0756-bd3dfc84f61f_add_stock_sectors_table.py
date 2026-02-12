"""add_stock_sectors_table

Revision ID: bd3dfc84f61f
Revises: 3e919c771399
Create Date: 2026-02-11 07:56:23.265624

Trading Analyst Database Migration
Creates stock_sectors table for caching stock-to-sector ETF mappings.
This reduces Yahoo Finance API calls since sector info rarely changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd3dfc84f61f'
down_revision: Union[str, Sequence[str], None] = '3e919c771399'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_sectors table with indexes."""
    op.create_table(
        "stock_sectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(10), nullable=False, unique=True),
        sa.Column("sector", sa.String(50), nullable=True),
        sa.Column("sector_etf", sa.String(10), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
    )
    op.create_index("ix_stock_sectors_id", "stock_sectors", ["id"])
    op.create_index("ix_stock_sectors_symbol", "stock_sectors", ["symbol"], unique=True)
    op.create_index("ix_stock_sectors_sector_etf", "stock_sectors", ["sector_etf"])
    op.create_index("ix_stock_sectors_created_at", "stock_sectors", ["created_at"])
    op.create_index("ix_stock_sectors_updated_at", "stock_sectors", ["updated_at"])
    op.create_index("ix_stock_sectors_deleted_at", "stock_sectors", ["deleted_at"])


def downgrade() -> None:
    """Drop stock_sectors table."""
    op.drop_table("stock_sectors")
