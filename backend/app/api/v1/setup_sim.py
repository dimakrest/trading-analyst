"""Setup simulation API routes."""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_data_service
from app.core.exceptions import APIError, SymbolNotFoundError
from app.schemas.setup_sim import (
    RunSetupSimulationRequest,
    SetupSimulationResponse,
)
from app.services.arena.agent_protocol import PriceBar
from app.services.data_service import DataService
from app.services.setup_sim_service import simulate_setup, run_simulation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/run",
    response_model=SetupSimulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Setup Simulation",
    description=(
        "Run a backtest simulation for user-defined trading setups against historical "
        "price data. Accepts multiple setups with entry prices and stop losses, fetches "
        "market data in parallel, and returns per-setup trade results with aggregate metrics."
    ),
    operation_id="run_setup_simulation",
    responses={
        422: {"description": "Invalid request (validation or unknown symbol)"},
        502: {"description": "Market data provider unavailable"},
    },
)
async def run_setup_simulation(
    request: RunSetupSimulationRequest,
    data_service: DataService = Depends(get_data_service),
) -> SetupSimulationResponse:
    """Run a setup simulation and return results synchronously."""
    # Determine unique symbols and date range
    symbols = list({s.symbol for s in request.setups})
    earliest_start = min(s.start_date for s in request.setups)

    logger.info(
        "Setup simulation: %d setups, %d symbols, %s to %s",
        len(request.setups), len(symbols), earliest_start, request.end_date,
    )

    # Fetch price data for all symbols in parallel
    async def fetch_symbol(symbol: str) -> tuple[str, list[PriceBar]]:
        records = await data_service.get_price_data(
            symbol=symbol,
            start_date=datetime.combine(
                earliest_start, datetime.min.time(), tzinfo=timezone.utc
            ),
            end_date=datetime.combine(
                request.end_date, datetime.max.time(), tzinfo=timezone.utc
            ),
            interval="1d",
        )
        bars = [
            PriceBar(
                date=r.timestamp.date(),
                open=Decimal(str(r.open_price)),
                high=Decimal(str(r.high_price)),
                low=Decimal(str(r.low_price)),
                close=Decimal(str(r.close_price)),
                volume=int(r.volume),
            )
            for r in records
        ]
        return symbol, bars

    try:
        results = await asyncio.gather(*[fetch_symbol(s) for s in symbols])
    except SymbolNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Symbol not found: {e}",
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Market data provider unavailable: {e}",
        )

    price_data: dict[str, list[PriceBar]] = dict(results)

    # Run simulation for each setup
    setup_results = []
    for setup in request.setups:
        bars = price_data.get(setup.symbol, [])
        result = simulate_setup(setup, bars, request.end_date)
        setup_results.append(result)

    return run_simulation(setup_results)
