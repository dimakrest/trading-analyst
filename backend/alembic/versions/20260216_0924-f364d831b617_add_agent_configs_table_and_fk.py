"""add_agent_configs_table_and_fk

Revision ID: f364d831b617
Revises: 0f07a028150e
Create Date: 2026-02-16 09:24:08.512072

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f364d831b617'
down_revision: Union[str, Sequence[str], None] = '0f07a028150e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema.

    Creates agent_configs table for storing named agent configurations,
    seeds a default CCI config, and adds FK to live20_runs.
    """
    # Create agent_configs table
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('agent_type', sa.String(50), nullable=False, server_default='live20'),
        sa.Column('scoring_algorithm', sa.String(20), nullable=False, server_default='cci'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.String(1000), nullable=True),
    )

    # Seed default config
    op.execute(
        "INSERT INTO agent_configs (name, agent_type, scoring_algorithm) "
        "VALUES ('Default CCI', 'live20', 'cci')"
    )

    # Add agent_config_id FK to live20_runs
    op.add_column('live20_runs', sa.Column(
        'agent_config_id', sa.Integer(),
        sa.ForeignKey('agent_configs.id', ondelete='SET NULL'),
        nullable=True,
    ))


def downgrade() -> None:
    """Downgrade database schema.

    Removes agent_config_id FK from live20_runs and drops agent_configs table.
    """
    # Remove FK from live20_runs
    op.drop_column('live20_runs', 'agent_config_id')

    # Drop agent_configs table (cascades to any remaining references)
    op.drop_table('agent_configs')
