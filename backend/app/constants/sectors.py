"""Sector ETF mapping for SPDR Select Sector ETFs.

Maps Yahoo Finance sector names to their corresponding SPDR ETF symbols.
Covers all 11 Select Sector SPDR ETFs (S&P 500 sector breakdown).
"""
import logging

logger = logging.getLogger(__name__)

# Yahoo Finance sector name → SPDR Select Sector ETF symbol
SECTOR_TO_ETF: dict[str, str] = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
}

# Pre-built lowercase lookup for O(1) case-insensitive matching
_SECTOR_TO_ETF_LOWER: dict[str, str] = {k.lower(): v for k, v in SECTOR_TO_ETF.items()}

# All valid sector ETF symbols (for endpoint validation)
VALID_SECTOR_ETFS: frozenset[str] = frozenset(SECTOR_TO_ETF.values())


def get_sector_etf(yahoo_sector: str | None) -> str | None:
    """Map a Yahoo Finance sector name to its SPDR ETF symbol.

    Case-insensitive lookup. Logs unmapped sectors for monitoring.

    Args:
        yahoo_sector: Sector name from Yahoo Finance (e.g., "Technology")

    Returns:
        SPDR ETF symbol (e.g., "XLK") or None if not mapped
    """
    if not yahoo_sector:
        return None
    sector_lower = yahoo_sector.strip().lower()
    if not sector_lower:
        return None
    etf = _SECTOR_TO_ETF_LOWER.get(sector_lower)
    if etf is None:
        logger.warning("Unmapped Yahoo sector: '%s' - consider adding to SECTOR_TO_ETF", yahoo_sector)
    return etf
