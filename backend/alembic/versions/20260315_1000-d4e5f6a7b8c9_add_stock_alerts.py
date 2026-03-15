"""add_stock_alerts

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-15 10:00:00.000000

Trading Analyst Database Migration
This migration was auto-generated using Alembic with async SQLAlchemy support.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stock_alerts and alert_events tables.

    stock_alerts stores alert configurations for monitoring symbols against
    technical setups (Fibonacci retracement or moving average). Each alert
    tracks its current status, configuration, and optional pre-computed state
    for frontend rendering.

    alert_events is an append-only audit log of every status transition that
    occurs on a stock alert, preserving the full history of market events.
    """
    # Create stock_alerts table
    op.create_table(
        'stock_alerts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('alert_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_paused', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('computed_state', sa.JSON(), nullable=True),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.String(1000), nullable=True),
    )
    op.create_index('ix_stock_alerts_symbol', 'stock_alerts', ['symbol'])
    op.create_index('ix_stock_alerts_alert_type', 'stock_alerts', ['alert_type'])
    op.create_index('ix_stock_alerts_status', 'stock_alerts', ['status'])
    op.create_index('ix_stock_alerts_is_active', 'stock_alerts', ['is_active'])

    # Create alert_events table
    op.create_table(
        'alert_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'alert_id',
            sa.Integer(),
            sa.ForeignKey('stock_alerts.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('previous_status', sa.String(30), nullable=True),
        sa.Column('new_status', sa.String(30), nullable=False),
        sa.Column('price_at_event', sa.Numeric(12, 4), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.String(1000), nullable=True),
    )
    op.create_index('ix_alert_events_alert_id', 'alert_events', ['alert_id'])


def downgrade() -> None:
    """Drop stock_alerts and alert_events tables.

    alert_events must be dropped first due to its foreign key reference to
    stock_alerts.
    """
    op.drop_index('ix_alert_events_alert_id', table_name='alert_events')
    op.drop_table('alert_events')

    op.drop_index('ix_stock_alerts_is_active', table_name='stock_alerts')
    op.drop_index('ix_stock_alerts_status', table_name='stock_alerts')
    op.drop_index('ix_stock_alerts_alert_type', table_name='stock_alerts')
    op.drop_index('ix_stock_alerts_symbol', table_name='stock_alerts')
    op.drop_table('stock_alerts')
