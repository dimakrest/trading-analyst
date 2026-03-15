"""Alert service for CRUD operations and alert state computation.

Handles:
- Alert creation with symbol validation
- Alert listing, updating, and soft deletion
- Fibonacci state computation using the fibonacci indicator module
- Moving Average state computation using analyze_ma_distance
- MA notification deduplication (fire only on transition TO at_ma)
"""
import logging
from datetime import datetime
from datetime import timezone
from typing import Any

import numpy as np

from app.core.exceptions import SymbolNotFoundError
from app.indicators.fibonacci import FibonacciState
from app.indicators.fibonacci import SwingPoint
from app.indicators.fibonacci import SwingStructure
from app.indicators.fibonacci import calculate_fib_levels
from app.indicators.fibonacci import compute_fibonacci_status
from app.indicators.fibonacci import find_latest_swing_structure
from app.indicators.ma_analysis import PricePosition
from app.indicators.ma_analysis import analyze_ma_distance
from app.models.alert import AlertEvent
from app.models.alert import StockAlert
from app.repositories.alert_repository import AlertRepository
from app.services.data_service import DataService

logger = logging.getLogger(__name__)

# Approaching band: distance_pct between tolerance and this threshold triggers "approaching"
_APPROACHING_THRESHOLD_PCT = 2.0

# Valid MA periods accepted for alert creation
VALID_MA_PERIODS = frozenset({20, 50, 150, 200})


class AlertService:
    """Service for alert CRUD and state computation.

    Separate from AlertMonitorService to enable lightweight use from API
    endpoints without coupling to the background polling loop.
    """

    def __init__(self, session_factory: Any, provider: Any) -> None:
        """Initialize with session factory and market data provider.

        Args:
            session_factory: async_sessionmaker for creating short-lived sessions.
            provider: MarketDataProviderInterface used by DataService.
        """
        self._session_factory = session_factory
        self._provider = provider

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_alert(
        self,
        symbol: str,
        alert_type: str,
        config: dict,
    ) -> list[StockAlert]:
        """Create one or more alerts.

        For moving_average alerts with a ma_periods list, this fans out to one
        StockAlert per period. Every other alert type creates exactly one record.

        Symbol validation is performed by fetching price data via DataService.
        A SymbolNotFoundError is raised if the symbol does not exist.

        Args:
            symbol: Stock ticker (will be uppercased).
            alert_type: "fibonacci" or "moving_average".
            config: Alert-type-specific configuration dict. For moving_average,
                may contain "ma_periods" list which triggers fan-out.

        Returns:
            List of created StockAlert instances (length >= 1).

        Raises:
            SymbolNotFoundError: If the symbol is not found by the data provider.
            ValueError: If alert_type is unrecognized.
        """
        symbol = symbol.upper().strip()

        # Validate symbol by fetching a small slice of price data
        data_service = DataService(
            session_factory=self._session_factory,
            provider=self._provider,
        )
        await data_service.get_price_data(symbol, interval="1d")
        # SymbolNotFoundError propagates to the caller if symbol is invalid

        if alert_type == "fibonacci":
            alert = await self._create_single_alert(symbol, alert_type, config)
            return [alert]

        if alert_type == "moving_average":
            ma_periods = config.get("ma_periods", [config.get("ma_period", 200)])
            if isinstance(ma_periods, int):
                ma_periods = [ma_periods]

            created: list[StockAlert] = []
            for period in ma_periods:
                per_period_config = {**config, "ma_period": period}
                per_period_config.pop("ma_periods", None)
                alert = await self._create_single_alert(symbol, alert_type, per_period_config)
                created.append(alert)
            return created

        raise ValueError(f"Unknown alert_type: {alert_type!r}")

    async def _create_single_alert(
        self, symbol: str, alert_type: str, config: dict
    ) -> StockAlert:
        """Create a single StockAlert record.

        Args:
            symbol: Validated, uppercased stock ticker.
            alert_type: "fibonacci" or "moving_average".
            config: Per-alert config dict.

        Returns:
            Persisted StockAlert instance.
        """
        initial_status = "no_structure" if alert_type == "fibonacci" else "above_ma"

        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alert = await repo.create(
                symbol=symbol,
                alert_type=alert_type,
                status=initial_status,
                config=config,
                is_active=True,
                is_paused=False,
                computed_state=None,
            )
            await session.commit()
            await session.refresh(alert)
        return alert

    async def get_alert(self, alert_id: int) -> StockAlert | None:
        """Get a single alert by ID (excludes soft-deleted).

        Args:
            alert_id: Primary key.

        Returns:
            StockAlert or None.
        """
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            return await repo.get_by_id(alert_id)

    async def list_alerts(
        self, filters: dict | None = None
    ) -> tuple[list[StockAlert], int]:
        """List alerts with optional filters and a total count.

        Args:
            filters: Optional dict with keys: status, alert_type, symbol.

        Returns:
            Tuple of (list of StockAlert, total count).
        """
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alerts = await repo.list_alerts(filters)
            count = await repo.count_alerts(filters)
        return alerts, count

    async def update_alert(
        self, alert_id: int, updates: dict
    ) -> StockAlert | None:
        """Update alert config or pause state.

        Args:
            alert_id: Primary key.
            updates: Dict of fields to update (config, is_paused, is_active).

        Returns:
            Updated StockAlert or None if not found.
        """
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alert = await repo.get_by_id(alert_id)
            if alert is None:
                return None

            for key, value in updates.items():
                if key in ("config", "is_paused", "is_active"):
                    setattr(alert, key, value)
            if hasattr(alert, "updated_at"):
                alert.updated_at = datetime.now(timezone.utc)

            await session.flush()
            await session.refresh(alert)
            await session.commit()
            return alert

    async def delete_alert(self, alert_id: int) -> bool:
        """Soft-delete an alert.

        Args:
            alert_id: Primary key.

        Returns:
            True if deleted, False if not found.
        """
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            alert = await repo.get_by_id(alert_id)
            if alert is None:
                return False

            alert.deleted_at = datetime.now(timezone.utc)
            alert.is_active = False
            if hasattr(alert, "updated_at"):
                alert.updated_at = datetime.now(timezone.utc)

            await session.flush()
            await session.commit()
        return True

    async def get_alert_events(self, alert_id: int) -> list[AlertEvent]:
        """Get event history for an alert, newest first.

        Args:
            alert_id: Primary key.

        Returns:
            List of AlertEvent instances.
        """
        async with self._session_factory() as session:
            repo = AlertRepository(session)
            return await repo.get_events_for_alert(alert_id)

    # ------------------------------------------------------------------
    # State computation
    # ------------------------------------------------------------------

    async def compute_alert_state(self, alert: StockAlert, price_data: list) -> dict:
        """Route to fibonacci or MA computation based on alert_type.

        Args:
            alert: StockAlert instance.
            price_data: List of PriceDataPoint objects from DataService.

        Returns:
            Dict with keys: status, computed_state, events.
        """
        if alert.alert_type == "fibonacci":
            return await self.compute_fibonacci_state(alert, price_data)
        if alert.alert_type == "moving_average":
            return await self.compute_ma_state(alert, price_data)
        raise ValueError(f"Unknown alert_type: {alert.alert_type!r}")

    async def compute_fibonacci_state(
        self, alert: StockAlert, price_data: list
    ) -> dict:
        """Compute Fibonacci retracement state using the fibonacci indicator module.

        Extracts OHLC arrays from price_data (list of PriceDataPoint), calls
        find_latest_swing_structure, calculate_fib_levels, and
        compute_fibonacci_status. Reconstructs the previous FibonacciState from
        alert.computed_state for continuity.

        Args:
            alert: StockAlert with alert_type == "fibonacci".
            price_data: List of PriceDataPoint objects.

        Returns:
            Dict with keys:
                status (str): New status string.
                computed_state (dict): JSON-serialisable state for frontend.
                events (list[dict]): Events generated during this computation.
        """
        if not price_data:
            return {
                "status": "no_structure",
                "computed_state": None,
                "events": [],
            }

        highs = np.array([float(p.high_price) for p in price_data])
        lows = np.array([float(p.low_price) for p in price_data])
        closes = np.array([float(p.close_price) for p in price_data])
        dates = [
            p.timestamp.strftime("%Y-%m-%d") if hasattr(p.timestamp, "strftime")
            else str(p.timestamp)[:10]
            for p in price_data
        ]

        current_price = float(closes[-1])
        config = alert.config or {}

        # Find the most recent valid swing structure
        swing_structure = find_latest_swing_structure(highs, lows, dates)

        # Calculate Fibonacci level prices if we have a structure
        fib_levels: dict[float, float] = {}
        if swing_structure is not None:
            fib_levels = calculate_fib_levels(
                swing_high=swing_structure.high.price,
                swing_low=swing_structure.low.price,
                direction=swing_structure.direction,
            )

        # Reconstruct previous FibonacciState from persisted computed_state
        previous_state = _deserialize_fibonacci_state(alert.computed_state)

        # Run state machine
        fib_state: FibonacciState = compute_fibonacci_status(
            current_price=current_price,
            swing_structure=swing_structure,
            fib_levels=fib_levels,
            config=config,
            previous_state=previous_state,
        )

        # Serialize computed_state for DB storage
        computed_state = _serialize_fibonacci_computed_state(fib_state)

        return {
            "status": fib_state.status,
            "computed_state": computed_state,
            "events": fib_state.events,
        }

    async def compute_ma_state(
        self, alert: StockAlert, price_data: list
    ) -> dict:
        """Compute Moving Average state using analyze_ma_distance.

        Checks candle count BEFORE calling analyze_ma_distance. If insufficient
        (< ma_period + 5), returns status="insufficient_data" without calling
        the indicator.

        MA notification deduplication: fires a status_change event only on
        transition TO "at_ma" (not while staying in it).

        Args:
            alert: StockAlert with alert_type == "moving_average".
            price_data: List of PriceDataPoint objects.

        Returns:
            Dict with keys:
                status (str): New status string.
                computed_state (dict): JSON-serialisable state for frontend.
                events (list[dict]): Events generated (at most 1 status_change).
        """
        config = alert.config or {}
        ma_period: int = int(config.get("ma_period", 200))
        tolerance_pct: float = float(config.get("tolerance_pct", 0.5))

        closes = [float(p.close_price) for p in price_data]
        candle_count = len(closes)
        required = ma_period + 5

        if candle_count < required:
            return {
                "status": "insufficient_data",
                "computed_state": {
                    "error": (
                        f"Insufficient price history for MA{ma_period} "
                        f"(need {required} candles, have {candle_count})"
                    )
                },
                "events": [],
            }

        analysis = analyze_ma_distance(
            closes=closes,
            period=ma_period,
            at_threshold_pct=tolerance_pct,
        )

        current_price = closes[-1]
        distance_pct = analysis.distance_pct

        # Determine status
        if analysis.price_position == PricePosition.AT:
            new_status = "at_ma"
        elif analysis.price_position == PricePosition.ABOVE:
            if 0 < distance_pct <= _APPROACHING_THRESHOLD_PCT:
                new_status = "approaching"
            else:
                new_status = "above_ma"
        else:
            # BELOW
            if -_APPROACHING_THRESHOLD_PCT <= distance_pct < 0:
                new_status = "approaching"
            else:
                new_status = "below_ma"

        # Compute events — fire only on transition TO at_ma (deduplication)
        previous_status = alert.status
        events: list[dict] = []

        if new_status == "at_ma" and previous_status != "at_ma":
            events.append({
                "event_type": "status_change",
                "previous_status": previous_status,
                "new_status": new_status,
                "price_at_event": current_price,
                "details": {
                    "ma_period": ma_period,
                    "ma_value": analysis.ma_value,
                    "distance_pct": distance_pct,
                },
            })

        computed_state = {
            "ma_value": analysis.ma_value,
            "ma_period": ma_period,
            "current_price": current_price,
            "distance_pct": distance_pct,
            "ma_slope": analysis.ma_slope.value,
        }

        return {
            "status": new_status,
            "computed_state": computed_state,
            "events": events,
        }


# ---------------------------------------------------------------------------
# Private helpers for (de)serialising FibonacciState
# ---------------------------------------------------------------------------


def _serialize_fibonacci_computed_state(fib_state: FibonacciState) -> dict | None:
    """Convert FibonacciState to the computed_state JSON structure.

    The fib_levels keys are formatted as strings with consistent decimal notation
    (e.g., "23.6", "38.2") so the frontend can use Record<string, FibLevelState>.

    Args:
        fib_state: Computed FibonacciState from the indicator.

    Returns:
        Dict matching the Phase 1 computed_state JSON schema, or None if no structure.
    """
    if fib_state.status == "no_structure":
        return None

    structure = fib_state.swing_structure
    if structure is None:
        return None

    # Serialize fib_levels with string keys (consistent formatting)
    serialized_levels: dict[str, dict] = {}
    for level_pct, detail in fib_state.fib_levels.items():
        key = _format_level_key(level_pct)
        serialized_levels[key] = {
            "price": detail.get("price"),
            "status": detail.get("status", "pending"),
            "triggered_at": detail.get("triggered_at"),
        }

    return {
        "swing_high": structure.high.price,
        "swing_low": structure.low.price,
        "swing_high_date": structure.high.date,
        "swing_low_date": structure.low.date,
        "trend_direction": structure.direction,
        "current_price": fib_state.current_price,
        "retracement_pct": fib_state.retracement_pct,
        "fib_levels": serialized_levels,
        "next_level": fib_state.next_level,
    }


def _format_level_key(level_pct: float) -> str:
    """Format a Fibonacci level percentage as a consistent string key.

    Produces keys like "23.6", "38.2", "50.0", "61.8", "78.6".

    Args:
        level_pct: Float level percentage.

    Returns:
        String key with exactly one decimal place.
    """
    return f"{level_pct:.1f}"


def _deserialize_fibonacci_state(
    computed_state: dict | None,
) -> FibonacciState | None:
    """Reconstruct a FibonacciState from a persisted computed_state dict.

    This allows the state machine in compute_fibonacci_status to use the
    previously triggered level history and swing structure for continuity.

    Args:
        computed_state: The JSON blob from StockAlert.computed_state, or None.

    Returns:
        FibonacciState or None if computed_state is absent or unparsable.
    """
    if not computed_state:
        return None

    try:
        swing_structure: SwingStructure | None = None
        swing_high_price = computed_state.get("swing_high")
        swing_low_price = computed_state.get("swing_low")
        swing_high_date = computed_state.get("swing_high_date", "")
        swing_low_date = computed_state.get("swing_low_date", "")
        trend_direction = computed_state.get("trend_direction", "uptrend")

        if swing_high_price is not None and swing_low_price is not None:
            # Index is unknown from stored state — use 1 and 0 as placeholders.
            # The _is_same_structure check uses price + direction, not index,
            # so placeholder indices do not cause incorrect re-anchor detection.
            swing_structure = SwingStructure(
                high=SwingPoint(index=1, price=float(swing_high_price), date=swing_high_date),
                low=SwingPoint(index=0, price=float(swing_low_price), date=swing_low_date),
                direction=trend_direction,
            )

        # Deserialize fib_levels from string keys back to float keys
        raw_levels: dict[str, dict] = computed_state.get("fib_levels", {})
        fib_levels: dict[float, dict] = {}
        for key, detail in raw_levels.items():
            try:
                fib_levels[float(key)] = {
                    "price": detail.get("price"),
                    "status": detail.get("status", "pending"),
                    "triggered_at": detail.get("triggered_at"),
                }
            except (ValueError, TypeError):
                continue

        return FibonacciState(
            status=computed_state.get("status", "no_structure"),
            swing_structure=swing_structure,
            fib_levels=fib_levels,
            retracement_pct=computed_state.get("retracement_pct"),
            next_level=computed_state.get("next_level"),
            current_price=float(computed_state.get("current_price", 0.0)),
            events=[],
        )
    except Exception:
        logger.warning("Failed to deserialize previous FibonacciState, starting fresh")
        return None
