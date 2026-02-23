"""add_trailing_stop_to_portfolio_configs

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-02-23 00:02:00.000000

Trading Analyst Database Migration
Adds trailing_stop_pct to portfolio_configs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e5f6a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trailing stop column to portfolio setups."""
    op.add_column(
        "portfolio_configs",
        sa.Column("trailing_stop_pct", sa.Float(), nullable=False, server_default="5.0"),
    )


def downgrade() -> None:
    """Remove trailing stop column from portfolio setups."""
    op.drop_column("portfolio_configs", "trailing_stop_pct")
