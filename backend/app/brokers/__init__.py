"""Broker integration package for order execution.

This package provides abstract interfaces and concrete implementations for
executing trades through various brokers. The design uses dependency injection
to allow switching between mock and live broker implementations.

Available brokers:
- MockBroker: Simulates order execution for testing and development
- IBBroker: Interactive Brokers integration (Phase 1 implemented)
"""
from app.brokers.base import BrokerError
from app.brokers.base import BrokerInterface
from app.brokers.base import OrderRequest
from app.brokers.base import OrderResult
from app.brokers.base import OrderStatus
from app.brokers.mock import MockBroker
from app.brokers.ib import IBBroker

__all__ = [
    "BrokerInterface",
    "BrokerError",
    "OrderStatus",
    "OrderRequest",
    "OrderResult",
    "MockBroker",
    "IBBroker",
]
