"""add_support_resistance_columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a1b2
Create Date: 2026-02-23 00:00:00.000000

Trading Analyst Database Migration
Adds support/resistance level columns (pivot, S1, R1) to recommendations table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add support/resistance level columns to recommendations.

    Columns are nullable because they are only populated for live_20 source
    recommendations, and older rows will not have values.
    """
    op.add_column(
        "recommendations",
        sa.Column("live20_pivot", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("live20_support_1", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column(
        "recommendations",
        sa.Column("live20_resistance_1", sa.Numeric(12, 4), nullable=True),
    )


def downgrade() -> None:
    """Remove support/resistance level columns from recommendations."""
    op.drop_column("recommendations", "live20_resistance_1")
    op.drop_column("recommendations", "live20_support_1")
    op.drop_column("recommendations", "live20_pivot")
