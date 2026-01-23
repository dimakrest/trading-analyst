"""Mock broker implementation for testing and development.

This module provides a mock broker that simulates order execution without
connecting to a real broker. Useful for:
- Local development
- Integration testing
- Demonstration purposes
"""
import logging
import uuid
from decimal import Decimal

from app.brokers.base import BrokerError
from app.brokers.base import BrokerInterface
from app.brokers.base import OrderRequest
from app.brokers.base import OrderResult
from app.brokers.base import OrderStatus

logger = logging.getLogger(__name__)


class MockBroker(BrokerInterface):
    """Mock broker implementation that simulates order execution.

    This broker provides realistic simulation of order execution:
    - Generates unique order IDs with MOCK- prefix
    - Always fills orders immediately at simulated price
    - Stores orders in memory for status queries
    - Supports order cancellation (though orders fill immediately)
    - Comprehensive logging for debugging

    The mock broker is useful for:
    - Testing execution service logic without broker dependency
    - Development without broker credentials
    - Demonstration and documentation

    Example:
        >>> broker = MockBroker()
        >>> request = OrderRequest(
        ...     ticker="AAPL",
        ...     quantity=100,
        ...     order_type="MARKET",
        ...     stop_loss_price=Decimal("150.00")
        ... )
        >>> result = await broker.place_order(request)
        >>> print(f"Order {result.order_id} filled at ${result.filled_price}")
    """

    def __init__(self):
        """Initialize mock broker with in-memory order storage."""
        self.orders: dict[str, OrderResult] = {}
        self.logger = logger
        self.logger.info("MockBroker initialized")

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place an order through the mock broker.

        This method simulates order execution by:
        1. Validating order parameters
        2. Generating a unique order ID (MOCK-{uuid})
        3. Simulating price (uses stop_loss_price + 1% as fill price)
        4. Immediately filling the order
        5. Storing order in memory

        Args:
            request: OrderRequest containing order details

        Returns:
            OrderResult with FILLED status and simulated execution details

        Raises:
            BrokerError: If order parameters are invalid

        Example:
            >>> request = OrderRequest(ticker="AAPL", quantity=100, order_type="MARKET")
            >>> result = await broker.place_order(request)
            >>> assert result.status == OrderStatus.FILLED
        """
        try:
            # Validate order parameters
            if not request.ticker:
                raise BrokerError("Ticker symbol is required")

            if request.quantity <= 0:
                raise BrokerError("Quantity must be positive")

            if not request.order_type:
                raise BrokerError("Order type is required")

            # Generate unique order ID
            order_id = f"MOCK-{uuid.uuid4()}"

            # Simulate fill price (use stop_loss_price + 1% as realistic simulation)
            # In real scenario, this would be current market price
            if request.stop_loss_price:
                # Assume entry is 1% above stop loss (typical for breakout trades)
                simulated_price = request.stop_loss_price * Decimal("1.01")
            else:
                # Fallback: use arbitrary price for testing
                simulated_price = Decimal("100.00")

            # Create result (mock broker always fills immediately)
            result = OrderResult(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_price=simulated_price,
                filled_quantity=request.quantity,
                error_message=None,
            )

            # Store order in memory
            self.orders[order_id] = result

            self.logger.info(
                f"MockBroker: Placed order {order_id} - "
                f"{request.quantity} shares of {request.ticker} "
                f"@ ${simulated_price} ({request.order_type})"
            )

            return result

        except BrokerError:
            # Re-raise broker errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            error_msg = f"Failed to place order: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise BrokerError(error_msg) from e

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get the current status of an order.

        This method retrieves order details from in-memory storage.

        Args:
            order_id: Unique order identifier from place_order()

        Returns:
            OrderResult with current order status

        Raises:
            BrokerError: If order ID is not found

        Example:
            >>> result = await broker.get_order_status("MOCK-123-456")
            >>> print(f"Order status: {result.status}")
        """
        if order_id not in self.orders:
            raise BrokerError(f"Order not found: {order_id}")

        result = self.orders[order_id]
        self.logger.debug(f"MockBroker: Retrieved status for order {order_id}: {result.status}")

        return result

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Note: Since MockBroker fills orders immediately, cancellation always
        returns False (order already filled). This is realistic for market orders.

        Args:
            order_id: Unique order identifier from place_order()

        Returns:
            False (orders are always filled in mock broker)

        Raises:
            BrokerError: If order ID is not found

        Example:
            >>> cancelled = await broker.cancel_order("MOCK-123-456")
            >>> print(f"Cancelled: {cancelled}")  # Always False for mock
        """
        if order_id not in self.orders:
            raise BrokerError(f"Order not found: {order_id}")

        # Since mock broker fills immediately, cannot cancel
        self.logger.info(
            f"MockBroker: Cancel requested for {order_id} but order already filled"
        )

        return False
