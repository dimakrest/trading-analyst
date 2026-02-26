"""convert_atr_to_percentage

Revision ID: 3e919c771399
Revises: a0e1c5237aca
Create Date: 2026-02-10 18:28:00.000000

Trading Analyst Database Migration
This migration converts live20_atr from dollar values to percentage values.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '3e919c771399'
down_revision: Union[str, Sequence[str], None] = 'a0e1c5237aca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Convert live20_atr from dollar values to percentages.

    Formula: atr_percentage = (atr_dollars / entry_price) * 100

    Only converts rows where both live20_atr and entry_price are non-null
    and entry_price > 0 to avoid division by zero.
    Nulls out ATR values that can't be converted to prevent data inconsistency.
    """
    # Convert existing ATR values from dollars to percentage
    op.execute("""
        UPDATE recommendations
        SET live20_atr = (live20_atr / entry_price) * 100
        WHERE live20_atr IS NOT NULL
          AND entry_price IS NOT NULL
          AND entry_price > 0
    """)

    # Null out ATR values that can't be converted (entry_price is null or zero)
    # This prevents orphaned dollar-denominated values in a percentage column
    op.execute("""
        UPDATE recommendations
        SET live20_atr = NULL
        WHERE live20_atr IS NOT NULL
          AND (entry_price IS NULL OR entry_price <= 0)
    """)


def downgrade() -> None:
    """
    Convert live20_atr from percentages back to dollar values.

    Formula: atr_dollars = (atr_percentage / 100) * entry_price

    Only converts rows where both live20_atr and entry_price are non-null
    and entry_price > 0.
    Nulls out ATR values that can't be converted to prevent data inconsistency.
    """
    # Convert ATR values back from percentage to dollars
    op.execute("""
        UPDATE recommendations
        SET live20_atr = (live20_atr / 100) * entry_price
        WHERE live20_atr IS NOT NULL
          AND entry_price IS NOT NULL
          AND entry_price > 0
    """)

    # Null out ATR values that can't be converted (entry_price is null or zero)
    # This prevents orphaned percentage values in a dollar-denominated column
    op.execute("""
        UPDATE recommendations
        SET live20_atr = NULL
        WHERE live20_atr IS NOT NULL
          AND (entry_price IS NULL OR entry_price <= 0)
    """)
