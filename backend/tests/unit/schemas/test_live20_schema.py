"""Unit tests for Live20 Pydantic schemas.

Tests schema-layer concerns:
- Field mapping from Recommendation model via from_recommendation()
- Serialization of Decimal fields to float for JSON
- Null/edge-case handling for S/R fields
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.schemas.live20 import Live20ResultResponse


def _make_mock_recommendation(**overrides):
    """Build a minimal mock Recommendation object with required fields set."""
    rec = MagicMock()
    rec.id = 1
    rec.stock = "AAPL"
    rec.created_at = datetime(2026, 2, 23, 10, 0, 0, tzinfo=timezone.utc)
    rec.live20_direction = "LONG"
    rec.confidence_score = 80
    rec.live20_trend_direction = "bearish"
    rec.live20_trend_aligned = True
    rec.live20_ma20_distance_pct = Decimal("-3.25")
    rec.live20_ma20_aligned = True
    rec.live20_candle_pattern = "hammer"
    rec.live20_candle_bullish = True
    rec.live20_candle_aligned = True
    rec.live20_candle_explanation = "Hammer reversal"
    rec.live20_volume_aligned = True
    rec.live20_volume_approach = "accumulation"
    rec.live20_atr = Decimal("3.5000")
    rec.live20_rvol = Decimal("1.50")
    rec.live20_cci_direction = "rising"
    rec.live20_cci_value = Decimal("-110.00")
    rec.live20_cci_zone = "oversold"
    rec.live20_cci_aligned = True
    rec.live20_scoring_algorithm = "cci"
    rec.live20_rsi2_value = None
    rec.live20_rsi2_score = None
    rec.live20_criteria_aligned = 4
    rec.live20_sector_etf = "XLK"
    # Support/Resistance defaults
    rec.live20_pivot = Decimal("128.6667")
    rec.live20_support_1 = Decimal("127.3334")
    rec.live20_resistance_1 = Decimal("130.3333")
    # Apply overrides
    for key, value in overrides.items():
        setattr(rec, key, value)
    return rec


class TestLive20ResultResponseFromRecommendation:
    """Tests for Live20ResultResponse.from_recommendation()."""

    def test_maps_support_resistance_fields(self):
        """from_recommendation() correctly maps S/R fields from the model."""
        rec = _make_mock_recommendation()

        response = Live20ResultResponse.from_recommendation(rec)

        assert response.pivot == Decimal("128.6667")
        assert response.support_1 == Decimal("127.3334")
        assert response.resistance_1 == Decimal("130.3333")

    def test_null_support_resistance_when_not_present(self):
        """from_recommendation() maps None S/R fields to None (old rows without data)."""
        rec = _make_mock_recommendation(
            live20_pivot=None,
            live20_support_1=None,
            live20_resistance_1=None,
        )

        response = Live20ResultResponse.from_recommendation(rec)

        assert response.pivot is None
        assert response.support_1 is None
        assert response.resistance_1 is None

    def test_support_resistance_serialized_as_float_in_json(self):
        """Decimal S/R fields serialize to float values in JSON output."""
        rec = _make_mock_recommendation()

        response = Live20ResultResponse.from_recommendation(rec)
        json_data = response.model_dump(mode="json")

        assert isinstance(json_data["pivot"], float)
        assert isinstance(json_data["support_1"], float)
        assert isinstance(json_data["resistance_1"], float)

        assert abs(json_data["pivot"] - 128.6667) < 1e-3
        assert abs(json_data["support_1"] - 127.3334) < 1e-3
        assert abs(json_data["resistance_1"] - 130.3333) < 1e-3

    def test_null_support_resistance_serialized_as_null_in_json(self):
        """None S/R fields serialize to null in JSON output."""
        rec = _make_mock_recommendation(
            live20_pivot=None,
            live20_support_1=None,
            live20_resistance_1=None,
        )

        response = Live20ResultResponse.from_recommendation(rec)
        json_data = response.model_dump(mode="json")

        assert json_data["pivot"] is None
        assert json_data["support_1"] is None
        assert json_data["resistance_1"] is None
