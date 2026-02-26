"""Interactive Brokers broker implementation.

This module provides a real broker integration with Interactive Brokers
TWS/Gateway for executing actual trades.
"""
import asyncio
import logging
from decimal import Decimal

from ib_async import Contract, IB, MarketOrder, Stock, StopOrder
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.base import (
    BrokerError,
    BrokerInterface,
    OrderRequest,
    OrderResult,
    OrderStatus,
)
from app.core.config import get_settings
from app.models.ib_order import IBOrderStatus
from app.repositories.ib_order_repository import IBOrderRepository


logger = logging.getLogger(__name__)


class IBBroker(BrokerInterface):
    """Interactive Brokers implementation of BrokerInterface.

    This broker connects to TWS or IB Gateway to execute real trades.
    Uses persistent connection with automatic reconnection handling.

    Configuration via environment variables:
    - IB_HOST: TWS/Gateway host (default: 127.0.0.1)
    - IB_PORT: TWS/Gateway port (7497=TWS paper, 7496=TWS live, 4002=Gateway paper, 4001=Gateway live)
    - IB_CLIENT_ID: Unique client identifier (default: 1)
    - IB_ACCOUNT: Account ID for multi-account setups (optional)

    Example:
        >>> broker = IBBroker()
        >>> await broker.connect()
        >>> result = await broker.place_order(OrderRequest(...))
        >>> await broker.disconnect()
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize IBBroker with configuration from settings.

        Args:
            db: Optional async database session for order persistence.
                 If None, orders are not persisted (useful for testing).
        """
        self.settings = get_settings()
        self.ib = IB()
        self._connected = False
        self.db = db
        self.order_repo = IBOrderRepository(db) if db else None
        self.logger = logger
        self.logger.info(
            f"IBBroker initialized (host={self.settings.ib_host}, "
            f"port={self.settings.ib_port}, client_id={self.settings.ib_client_id})"
        )

    async def connect(self) -> None:
        """Establish connection to TWS/Gateway.

        Raises:
            BrokerError: If connection fails after timeout
        """
        if self._connected:
            self.logger.debug("Already connected to IB")
            return

        try:
            self.logger.info(
                f"Connecting to IB at {self.settings.ib_host}:{self.settings.ib_port}"
            )
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.settings.ib_host,
                    port=self.settings.ib_port,
                    clientId=self.settings.ib_client_id,
                    readonly=False,  # Need write access for orders
                ),
                timeout=self.settings.ib_connection_timeout,
            )
            self._connected = True
            self.logger.info("Successfully connected to IB")

            # Validate configured account matches actual IB account
            if self.settings.ib_account:
                # Get list of accounts available in this IB session
                managed_accounts = self.ib.managedAccounts()

                if not managed_accounts:
                    error_msg = (
                        "No accounts found in IB Gateway session. "
                        "Ensure you are logged into IB Gateway with a valid account."
                    )
                    self.logger.error(error_msg)
                    self._connected = False
                    self.ib.disconnect()
                    raise BrokerError(error_msg)

                # Verify configured account is in the list of managed accounts
                if self.settings.ib_account not in managed_accounts:
                    error_msg = (
                        f"Account mismatch: Configured IB_ACCOUNT='{self.settings.ib_account}' "
                        f"not found in IB Gateway session. "
                        f"Available accounts: {', '.join(managed_accounts)}. "
                        f"Either update IB_ACCOUNT in .env to match your IB Gateway login, "
                        f"or log into IB Gateway with account '{self.settings.ib_account}'."
                    )
                    self.logger.error(error_msg)
                    self._connected = False
                    self.ib.disconnect()
                    raise BrokerError(error_msg)

                self.logger.info(
                    f"Account validated: {self.settings.ib_account} (available: {', '.join(managed_accounts)})"
                )

                # Subscribe to P&L updates for the account
                try:
                    self.ib.reqPnL(self.settings.ib_account)
                    self.logger.info(f"P&L subscription active for account {self.settings.ib_account}")
                except Exception as e:
                    self.logger.error(
                        f"Failed to subscribe to P&L updates for {self.settings.ib_account}: {e}. "
                        f"P&L values will remain None, status bar will handle this gracefully."
                    )
                    # P&L will remain None, status bar will show this gracefully

        except asyncio.TimeoutError:
            error_msg = (
                f"Connection to IB timed out after {self.settings.ib_connection_timeout}s. "
                f"Ensure TWS/Gateway is running and API connections are enabled."
            )
            self.logger.error(error_msg)
            raise BrokerError(error_msg)
        except Exception as e:
            error_msg = f"Failed to connect to IB: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise BrokerError(error_msg) from e

    async def disconnect(self) -> None:
        """Disconnect from TWS/Gateway gracefully."""
        if self._connected:
            self.logger.info("Disconnecting from IB")
            self.ib.disconnect()
            self._connected = False
            self.logger.info("Disconnected from IB")

    async def _ensure_connected(self) -> None:
        """Ensure connection is active, reconnecting if needed.

        Raises:
            BrokerError: If reconnection fails
        """
        if not self._connected or not self.ib.isConnected():
            self.logger.warning("IB connection lost, attempting reconnect...")
            self._connected = False
            await self.connect()

    def _create_contract(self, ticker: str) -> Contract:
        """Create IB contract for US stock.

        Args:
            ticker: Stock symbol (e.g., "AAPL")

        Returns:
            Contract: IB contract object
        """
        return Stock(ticker, "SMART", "USD")

    def _make_composite_order_id(self, entry_id: int, stop_id: int | None) -> str:
        """Create composite order ID from entry and stop order IDs.

        Args:
            entry_id: IB order ID for entry order
            stop_id: IB order ID for stop order (None if not placed)

        Returns:
            str: Composite order ID in format "IB-{entry}:{stop}" or "IB-{entry}:none"
        """
        stop_str = str(stop_id) if stop_id else "none"
        return f"IB-{entry_id}:{stop_str}"

    def _parse_composite_order_id(self, order_id: str) -> tuple[int, int | None]:
        """Parse composite order ID into entry and stop order IDs.

        Args:
            order_id: Composite order ID

        Returns:
            tuple: (entry_order_id, stop_order_id or None)

        Raises:
            BrokerError: If order ID format is invalid
        """
        if not order_id.startswith("IB-"):
            raise BrokerError(f"Invalid IB order ID format: {order_id}")

        try:
            parts = order_id[3:].split(":")
            entry_id = int(parts[0])
            stop_id = int(parts[1]) if parts[1] != "none" else None
            return entry_id, stop_id
        except (IndexError, ValueError) as e:
            raise BrokerError(f"Invalid IB order ID format: {order_id}") from e

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place entry order with linked stop-loss through IB.

        Uses parentId linking to create atomic bracket-style order:
        - Entry and stop orders submitted together
        - Stop only activates after entry fills (IB manages this)
        - No unprotected position window

        Args:
            request: OrderRequest with ticker, quantity, and stop_loss_price

        Returns:
            OrderResult with composite order ID and fill details

        Raises:
            BrokerError: If order placement fails
        """
        await self._ensure_connected()

        # Validate request
        if not request.ticker:
            raise BrokerError("Ticker symbol is required")
        if request.quantity <= 0:
            raise BrokerError("Quantity must be positive")
        if not request.stop_loss_price:
            raise BrokerError("Stop loss price is required for IB orders")

        try:
            # Create and qualify contract
            contract = self._create_contract(request.ticker)
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                raise BrokerError(f"Invalid or unknown symbol: {request.ticker}")

            self.logger.info(
                f"Placing bracket order: {request.quantity} {request.ticker} "
                f"with stop @ ${request.stop_loss_price}"
            )

            # Create parent (entry) order with explicit ID
            entry_order = MarketOrder("BUY", request.quantity)
            entry_order.orderId = self.ib.client.getReqId()
            entry_order.transmit = False  # Hold until stop is ready

            # Create stop order linked to parent
            # Note: IB API requires float for price, not Decimal
            stop_order = StopOrder(
                "SELL", request.quantity, float(request.stop_loss_price)
            )
            stop_order.orderId = self.ib.client.getReqId()
            stop_order.parentId = entry_order.orderId  # KEY: Link to parent
            stop_order.transmit = True  # Transmit both orders

            # Place both orders (stop won't activate until entry fills)
            entry_trade = self.ib.placeOrder(contract, entry_order)
            stop_trade = self.ib.placeOrder(contract, stop_order)

            self.logger.info(
                f"Orders submitted - Entry: {entry_order.orderId}, Stop: {stop_order.orderId}"
            )

            # Wait for entry to fill
            filled_price = await self._wait_for_fill(entry_trade, request.ticker)

            if filled_price is None:
                # Entry failed - stop was never activated (parentId behavior)
                status = self._map_ib_status(entry_trade.orderStatus.status)
                error_msg = f"Entry order failed: {entry_trade.orderStatus.status}"
                self.logger.error(error_msg)
                return OrderResult(
                    order_id=self._make_composite_order_id(
                        entry_order.orderId, stop_order.orderId
                    ),
                    status=status,
                    filled_price=None,
                    filled_quantity=None,
                    error_message=error_msg,
                )

            self.logger.info(
                f"Entry filled: {request.quantity} {request.ticker} @ ${filled_price} "
                f"(stop order now active)"
            )

            # Create composite order ID
            composite_id = self._make_composite_order_id(
                entry_order.orderId, stop_order.orderId
            )

            # Persist order mapping to database
            if self.order_repo:
                await self.order_repo.create_order(
                    composite_order_id=composite_id,
                    entry_order_id=entry_order.orderId,
                    stop_order_id=stop_order.orderId,
                    symbol=request.ticker,
                    quantity=request.quantity,
                    stop_price=request.stop_loss_price,
                    filled_price=filled_price,
                    status=IBOrderStatus.FILLED,
                )
                self.logger.info(f"Persisted order mapping: {composite_id}")

            return OrderResult(
                order_id=composite_id,
                status=OrderStatus.FILLED,
                filled_price=filled_price,
                filled_quantity=request.quantity,
                error_message=None,
            )

        except BrokerError:
            raise
        except Exception as e:
            error_msg = f"Failed to place order: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise BrokerError(error_msg) from e

    async def _wait_for_fill(self, trade, ticker: str) -> Decimal | None:
        """Wait for order to fill with timeout.

        Args:
            trade: IB Trade object to monitor
            ticker: Symbol for logging

        Returns:
            Fill price as Decimal if filled, None if rejected/timeout
        """
        timeout = self.settings.ib_order_timeout
        start_time = asyncio.get_running_loop().time()

        while True:
            # Check if done
            if trade.isDone():
                if trade.orderStatus.status == "Filled":
                    # Get average fill price
                    if trade.fills:
                        avg_price = sum(
                            f.execution.price * f.execution.shares for f in trade.fills
                        ) / sum(f.execution.shares for f in trade.fills)
                        return Decimal(str(avg_price))
                    return Decimal(str(trade.orderStatus.avgFillPrice))
                else:
                    # Cancelled or rejected
                    self.logger.warning(
                        f"Order for {ticker} ended with status: {trade.orderStatus.status}"
                    )
                    return None

            # Check timeout
            elapsed = asyncio.get_running_loop().time() - start_time
            if elapsed > timeout:
                self.logger.error(f"Order for {ticker} timed out after {timeout}s")
                # Try to cancel the timed out order
                self.ib.cancelOrder(trade.order)
                return None

            # Check connection and reconnect if needed
            if not self.ib.isConnected():
                self.logger.warning("Connection lost during fill wait, reconnecting...")
                await self._ensure_connected()

            # Wait for updates - use asyncio.sleep for consistent async behavior
            await asyncio.sleep(self.settings.ib_fill_poll_interval)

    def _map_ib_status(self, ib_status: str) -> OrderStatus:
        """Map IB order status to our OrderStatus enum.

        Args:
            ib_status: IB status string

        Returns:
            OrderStatus enum value
        """
        status_map = {
            "PendingSubmit": OrderStatus.PENDING,
            "PendingCancel": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.PENDING,
            "Submitted": OrderStatus.PENDING,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.REJECTED,
            "ApiCancelled": OrderStatus.CANCELLED,
        }
        return status_map.get(ib_status, OrderStatus.REJECTED)

    async def get_order_status(self, order_id: str) -> OrderResult:
        """Get combined status of entry and stop orders.

        Looks up order in database first, then queries IB for current status.
        Falls back to direct IB query if database is not available.

        Args:
            order_id: Composite order ID from place_order()

        Returns:
            OrderResult with combined status

        Raises:
            BrokerError: If order ID is invalid or not found
        """
        await self._ensure_connected()

        # Look up order in database
        if self.order_repo:
            db_order = await self.order_repo.get_by_composite_id(order_id)
            if db_order:
                # Query IB for current status using stored order IDs
                entry_trade = None
                stop_trade = None
                for trade in self.ib.trades():
                    if trade.order.orderId == db_order.entry_order_id:
                        entry_trade = trade
                    elif db_order.stop_order_id and trade.order.orderId == db_order.stop_order_id:
                        stop_trade = trade

                if entry_trade:
                    entry_status = self._map_ib_status(entry_trade.orderStatus.status)

                    # Atomically update database status if changed (prevents race conditions)
                    new_status = self._determine_combined_status(entry_status, stop_trade)
                    if new_status.value != db_order.status:
                        await self.order_repo.update_status_if_changed(
                            order_id, db_order.status, new_status
                        )

                    return OrderResult(
                        order_id=order_id,
                        status=entry_status,
                        filled_price=db_order.filled_price,
                        filled_quantity=db_order.quantity if entry_status == OrderStatus.FILLED else None,
                        error_message=None,
                    )

                # Entry trade not found in IB (session expired), return cached status
                self.logger.warning(
                    f"Entry trade {db_order.entry_order_id} not found in IB session, "
                    f"using cached status for order {order_id}"
                )
                return OrderResult(
                    order_id=order_id,
                    status=self._map_db_status_to_order_status(db_order.status),
                    filled_price=db_order.filled_price,
                    filled_quantity=db_order.quantity if db_order.status in [IBOrderStatus.FILLED.value, IBOrderStatus.STOPPED.value] else None,
                    error_message=None,
                )

        # No database - fall back to parsing ID and querying IB directly
        # (Keep existing fallback logic for backwards compatibility and testing)
        entry_id, stop_id = self._parse_composite_order_id(order_id)

        # Find orders in IB's order list
        entry_trade = None
        stop_trade = None
        for trade in self.ib.trades():
            if trade.order.orderId == entry_id:
                entry_trade = trade
            elif stop_id and trade.order.orderId == stop_id:
                stop_trade = trade

        if not entry_trade:
            raise BrokerError(f"Entry order not found: {entry_id}")

        entry_status = self._map_ib_status(entry_trade.orderStatus.status)

        return OrderResult(
            order_id=order_id,
            status=entry_status,
            filled_price=Decimal(str(entry_trade.orderStatus.avgFillPrice))
            if entry_trade.orderStatus.avgFillPrice
            else None,
            filled_quantity=int(entry_trade.orderStatus.filled)
            if entry_trade.orderStatus.filled
            else None,
            error_message=None,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel entry and stop orders.

        If entry is already filled, only cancels the stop order.
        If entry is pending, cancels both.

        Args:
            order_id: Composite order ID from place_order()

        Returns:
            True if any order was cancelled, False if all already filled

        Raises:
            BrokerError: If order ID is invalid or not found
        """
        await self._ensure_connected()

        entry_id, stop_id = self._parse_composite_order_id(order_id)

        cancelled_any = False

        # Find and cancel orders
        for trade in self.ib.trades():
            if trade.order.orderId == entry_id:
                if trade.orderStatus.status not in ["Filled", "Cancelled"]:
                    self.logger.info(f"Cancelling entry order {entry_id}")
                    self.ib.cancelOrder(trade.order)
                    cancelled_any = True
                else:
                    self.logger.info(f"Entry order {entry_id} already {trade.orderStatus.status}")

            elif stop_id and trade.order.orderId == stop_id:
                if trade.orderStatus.status not in ["Filled", "Cancelled"]:
                    self.logger.info(f"Cancelling stop order {stop_id}")
                    self.ib.cancelOrder(trade.order)
                    cancelled_any = True
                else:
                    self.logger.info(f"Stop order {stop_id} already {trade.orderStatus.status}")

        # Wait briefly for cancellation to process
        await asyncio.sleep(self.settings.ib_cancel_wait_time)

        # Update database status if cancellation succeeded
        if cancelled_any and self.order_repo:
            await self.order_repo.update_status(order_id, IBOrderStatus.CANCELLED)
            self.logger.info(f"Updated order {order_id} status to CANCELLED in database")

        return cancelled_any

    def _determine_combined_status(self, entry_status: OrderStatus, stop_trade) -> IBOrderStatus:
        """Determine combined order status from entry and stop trade states.

        Args:
            entry_status: Status of the entry order
            stop_trade: IB Trade object for stop order (or None)

        Returns:
            IBOrderStatus: Combined status of the order pair
        """
        if entry_status == OrderStatus.CANCELLED:
            return IBOrderStatus.CANCELLED
        elif entry_status == OrderStatus.REJECTED:
            return IBOrderStatus.REJECTED
        elif entry_status == OrderStatus.FILLED:
            # Check if stop was triggered
            if stop_trade and self._map_ib_status(stop_trade.orderStatus.status) == OrderStatus.FILLED:
                return IBOrderStatus.STOPPED
            return IBOrderStatus.FILLED
        return IBOrderStatus.PENDING

    def _map_db_status_to_order_status(self, db_status: str) -> OrderStatus:
        """Map IBOrderStatus (DB) to OrderStatus (API response).

        IBOrderStatus has STOPPED which doesn't exist in OrderStatus.
        STOPPED means the stop order was triggered, so the position is closed
        - semantically equivalent to FILLED from the caller's perspective.

        Args:
            db_status: Status from database (IBOrderStatus value)

        Returns:
            OrderStatus: API response status
        """
        mapping = {
            IBOrderStatus.PENDING.value: OrderStatus.PENDING,
            IBOrderStatus.FILLED.value: OrderStatus.FILLED,
            IBOrderStatus.CANCELLED.value: OrderStatus.CANCELLED,
            IBOrderStatus.REJECTED.value: OrderStatus.REJECTED,
            IBOrderStatus.STOPPED.value: OrderStatus.FILLED,  # Stop executed = position closed
        }
        return mapping.get(db_status, OrderStatus.PENDING)
