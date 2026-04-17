"""add_circuit_breaker_and_regime_to_arena_snapshots

Revision ID: f5a6b7c8d9e0
Revises: e4f013928c7e
Create Date: 2026-04-16 10:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, Sequence[str], None] = 'e4f013928c7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add circuit_breaker_state, circuit_breaker_atr_pct, regime_state to arena_snapshots.

    Pre-existing rows receive circuit_breaker_state='disabled' from the server default,
    matching their actual state (no breaker config on older simulations).
    circuit_breaker_atr_pct and regime_state default to NULL.
    """
    op.add_column(
        "arena_snapshots",
        sa.Column(
            "circuit_breaker_state",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'disabled'"),
        ),
    )
    op.add_column(
        "arena_snapshots",
        sa.Column("circuit_breaker_atr_pct", sa.Numeric(8, 4), nullable=True),
    )
    op.add_column(
        "arena_snapshots",
        sa.Column("regime_state", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    """Remove circuit_breaker_state, circuit_breaker_atr_pct, regime_state from arena_snapshots."""
    op.drop_column("arena_snapshots", "regime_state")
    op.drop_column("arena_snapshots", "circuit_breaker_atr_pct")
    op.drop_column("arena_snapshots", "circuit_breaker_state")
