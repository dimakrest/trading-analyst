"""add_position_size_and_min_score_to_portfolio_configs

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-02-23 00:01:00.000000

Trading Analyst Database Migration
Adds position_size and min_buy_score to portfolio_configs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5f6a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add position sizing and min score columns to portfolio setups."""
    op.add_column(
        "portfolio_configs",
        sa.Column("position_size", sa.Integer(), nullable=False, server_default="1000"),
    )
    op.add_column(
        "portfolio_configs",
        sa.Column("min_buy_score", sa.Integer(), nullable=False, server_default="60"),
    )


def downgrade() -> None:
    """Remove added columns from portfolio setups."""
    op.drop_column("portfolio_configs", "min_buy_score")
    op.drop_column("portfolio_configs", "position_size")
