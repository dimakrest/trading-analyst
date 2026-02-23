"""add_signal_score_columns

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-02-22 00:00:00.000000

Trading Analyst Database Migration
Adds configurable non-trend signal score weights to agent_configs and live20_runs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add configurable signal score weight columns.

    Trend is now an eligibility filter (non-scoring), and these 4 fields define
    the 100-point score allocation across non-trend criteria.
    """
    # agent_configs: persisted user-defined score weights
    op.add_column(
        "agent_configs",
        sa.Column("volume_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "agent_configs",
        sa.Column("candle_pattern_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "agent_configs",
        sa.Column("cci_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "agent_configs",
        sa.Column("ma20_distance_score", sa.Integer(), nullable=False, server_default="25"),
    )

    # live20_runs: denormalized snapshot of weights used during run execution
    op.add_column(
        "live20_runs",
        sa.Column("volume_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "live20_runs",
        sa.Column("candle_pattern_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "live20_runs",
        sa.Column("cci_score", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "live20_runs",
        sa.Column("ma20_distance_score", sa.Integer(), nullable=False, server_default="25"),
    )


def downgrade() -> None:
    """Remove configurable signal score weight columns."""
    op.drop_column("live20_runs", "ma20_distance_score")
    op.drop_column("live20_runs", "cci_score")
    op.drop_column("live20_runs", "candle_pattern_score")
    op.drop_column("live20_runs", "volume_score")

    op.drop_column("agent_configs", "ma20_distance_score")
    op.drop_column("agent_configs", "cci_score")
    op.drop_column("agent_configs", "candle_pattern_score")
    op.drop_column("agent_configs", "volume_score")
