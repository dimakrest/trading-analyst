"""add_portfolio_configs_table

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-02-23 00:00:00.000000

Trading Analyst Database Migration
Adds portfolio_configs table for reusable portfolio setup presets.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create portfolio_configs table."""
    op.create_table(
        "portfolio_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "portfolio_strategy",
            sa.String(length=64),
            nullable=False,
            server_default="none",
        ),
        sa.Column("max_per_sector", sa.Integer(), nullable=True),
        sa.Column("max_open_positions", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    """Drop portfolio_configs table."""
    op.drop_table("portfolio_configs")
