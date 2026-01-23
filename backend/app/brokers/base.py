"""Abstract broker interface and common data structures.

This module defines the contract that all broker implementations must follow.
It provides type-safe order management through dataclasses and enums.
"""
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class OrderStatus(str, Enum):
    """Order status values returned by broker operations.

    These statuses represent the lifecycle of an order:
    - PENDING: Order submitted but not yet filled
    - FILLED: Order successfully executed
    - CANCELLED: Order was cancelled before execution
    - REJECTED: Broker rejected the order (insufficient funds, invalid parameters, etc.)
    """
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class OrderRequest:
    """Represents a request to place an order through the broker.

    This dataclass captures all information needed to execute a trade:
    - ticker: Stock symbol (e.g., "AAPL")
    - quantity: Number of shares to buy
    - order_type: Type of order (e.g., "MARKET", "STOP")
    - stop_loss_price: Stop loss price for risk management

    Example:
        >>> request = OrderRequest(
        ...     ticker="AAPL",
        ...     quantity=100,
        ...     order_type="MARKET",
        ...     stop_loss_price=Decimal("150.00")
        ... )
    """
    ticker: str
    quantity: int
    order_type: str  # "MARKET", "STOP", etc.
    stop_loss_price: Decimal | None = None


@dataclass
class OrderResult:
    """Represents the result of placing an order through the broker.

    This dataclass contains all information returned after order execution:
    - order_id: Unique identifier from the broker (e.g., "MOCK-123-456")
    - status: Current status of the order (FILLED, PENDING, etc.)
    - filled_price: Price at which order was filled (None if not filled)
    - filled_quantity: Number of shares filled (may be partial)
    - error_message: Error details if status is REJECTED

    Example:
        >>> result = OrderResult(
        ...     order_id="MOCK-abc-def",
        ...     status=OrderStatus.FILLED,
        ...     filled_price=Decimal("150.25"),
        ...     filled_quantity=100,
        ...     error_message=None
        ... )
    """
    order_id: str
    status: OrderStatus
    filled_price: Decimal | None = None
    filled_quantity: int | None = None
    error_message: str | None = None


class BrokerError(Exception):
    """Base exception for broker operations.

    This exception is raised when broker operations fail due to:
    - Connection issues
    - Invalid order parameters
    - Insufficient funds
    - Market closed
    - API errors

    Example:
        >>> raise BrokerError("Failed to connect to broker API")
    """


class BrokerInterface(ABC):
    """Abstract interface that all broker implementations must follow.

    This interface defines the contract for broker operations. Concrete
    implementations (MockBroker, IBBroker) must implement all abstract methods.

    The interface uses dependency injection pattern to allow easy swapping
    between mock and live brokers without changing service code.

    Methods:
        place_order: Submit an order to the broker
        get_order_status: Check the current status of an order
        cancel_order: Cancel a pending order

    Example:
        >>> class MyBroker(BrokerInterface):
        ...     async def place_order(self, request: OrderRequest) -> OrderResult:
        ...         # Implementation here
        ...         pass
    """

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place an order through the broker.

        This method submits an order to the broker and returns the result.
        The order may be filled immediately (market orders) or remain pending
        (limit/stop orders).

        Args:
            request: OrderRequest containing order details

        Returns:
            OrderResult with order ID, status, and execution details

        Raises:
            BrokerError: If order placement fails

        Example:
            >>> request = OrderRequest(ticker="AAPL", quantity=100, order_type="MARKET")
            >>> result = await broker.place_order(request)
            >>> print(f"Order {result.order_id} status: {result.status}")
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get the current status of an order.

        This method queries the broker for the current state of an order.
        Useful for checking if pending orders have been filled.

        Args:
            order_id: Unique order identifier from place_order()

        Returns:
            OrderResult with current order status and details

        Raises:
            BrokerError: If order ID is invalid or query fails

        Example:
            >>> result = await broker.get_order_status("ORDER-123")
            >>> if result.status == OrderStatus.FILLED:
            ...     print(f"Filled at ${result.filled_price}")
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        This method attempts to cancel an order that hasn't been filled yet.
        Only PENDING orders can be cancelled.

        Args:
            order_id: Unique order identifier from place_order()

        Returns:
            True if order was cancelled successfully, False if already filled

        Raises:
            BrokerError: If order ID is invalid or cancellation fails

        Example:
            >>> cancelled = await broker.cancel_order("ORDER-123")
            >>> if cancelled:
            ...     print("Order cancelled successfully")
        """
        pass
