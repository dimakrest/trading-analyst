"""add_sr_touch_count_columns

Revision ID: b3c4d5e6f7a8
Revises: f6a7b8c9d0e1
Create Date: 2026-02-24 01:00:00.000000

Trading Analyst Database Migration
Adds live20_support_1_touches and live20_resistance_1_touches columns to
recommendations table for cluster-based support/resistance touch counts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add touch count columns for cluster-based S/R levels."""
    op.add_column(
        "recommendations",
        sa.Column("live20_support_1_touches", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("live20_resistance_1_touches", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove touch count columns."""
    op.drop_column("recommendations", "live20_resistance_1_touches")
    op.drop_column("recommendations", "live20_support_1_touches")
