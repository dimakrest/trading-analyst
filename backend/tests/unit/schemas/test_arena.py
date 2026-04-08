"""Unit tests for Arena schema validation.

Tests Pydantic-level validation for CreateSimulationRequest and
CreateComparisonRequest — no DB or HTTP needed.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.arena import CreateComparisonRequest, CreateSimulationRequest


# ---------------------------------------------------------------------------
# Helpers — minimal valid kwargs for each schema
# ---------------------------------------------------------------------------

def _sim_kwargs(**overrides) -> dict:
    """Return minimal valid kwargs for CreateSimulationRequest."""
    base = {
        "symbols": ["AAPL"],
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 3, 31),
    }
    base.update(overrides)
    return base


def _cmp_kwargs(**overrides) -> dict:
    """Return minimal valid kwargs for CreateComparisonRequest."""
    base = {
        "symbols": ["AAPL"],
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 3, 31),
        "portfolio_strategies": ["none", "score_sector_low_atr"],
    }
    base.update(overrides)
    return base


# ===========================================================================
# CreateSimulationRequest tests
# ===========================================================================


class TestCreateSimulationSizingMode:
    """Validate sizing_mode and the risk_based + stop_type cross-field constraint."""

    @pytest.mark.unit
    def test_rejects_unknown_sizing_mode(self) -> None:
        """sizing_mode must be one of 'fixed', 'fixed_pct', 'risk_based'."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSimulationRequest(**_sim_kwargs(sizing_mode="bogus"))

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("sizing_mode",) for e in errors)

    @pytest.mark.unit
    def test_rejects_risk_based_with_fixed_stop(self) -> None:
        """sizing_mode='risk_based' requires stop_type='atr'."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSimulationRequest(
                **_sim_kwargs(sizing_mode="risk_based", stop_type="fixed")
            )

        # model_validator raises a ValueError; Pydantic wraps it
        assert "sizing_mode='risk_based' requires stop_type='atr'" in str(
            exc_info.value
        )

    @pytest.mark.unit
    def test_accepts_risk_based_with_atr_stop(self) -> None:
        """Happy path: risk_based + atr stop should validate without error."""
        req = CreateSimulationRequest(
            **_sim_kwargs(sizing_mode="risk_based", stop_type="atr")
        )

        assert req.sizing_mode == "risk_based"
        assert req.stop_type == "atr"

    @pytest.mark.unit
    def test_accepts_fixed_sizing_mode(self) -> None:
        """Default sizing_mode='fixed' with default stop_type='fixed' is valid."""
        req = CreateSimulationRequest(**_sim_kwargs())

        assert req.sizing_mode == "fixed"
        assert req.stop_type == "fixed"

    @pytest.mark.unit
    def test_accepts_fixed_pct_sizing_mode(self) -> None:
        """sizing_mode='fixed_pct' is valid when position_size_pct is set."""
        req = CreateSimulationRequest(
            **_sim_kwargs(
                sizing_mode="fixed_pct",
                stop_type="atr",
                position_size_pct=33.0,
            )
        )

        assert req.sizing_mode == "fixed_pct"
        assert req.position_size_pct == 33.0

    @pytest.mark.unit
    def test_rejects_fixed_pct_without_position_size_pct(self) -> None:
        """sizing_mode='fixed_pct' requires position_size_pct."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSimulationRequest(**_sim_kwargs(sizing_mode="fixed_pct"))

        msg = str(exc_info.value)
        assert "fixed_pct" in msg
        assert "position_size_pct" in msg

    @pytest.mark.unit
    def test_rejects_unknown_stop_type(self) -> None:
        """stop_type must be one of 'fixed', 'atr'."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSimulationRequest(**_sim_kwargs(stop_type="trailing"))

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("stop_type",) for e in errors)


# ===========================================================================
# CreateComparisonRequest tests
# ===========================================================================


class TestCreateComparisonSizingMode:
    """Validate sizing_mode and risk_based + stop_type constraint on comparisons."""

    @pytest.mark.unit
    def test_rejects_unknown_sizing_mode(self) -> None:
        """sizing_mode must be one of 'fixed', 'fixed_pct', 'risk_based'."""
        with pytest.raises(ValidationError) as exc_info:
            CreateComparisonRequest(**_cmp_kwargs(sizing_mode="bogus"))

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("sizing_mode",) for e in errors)

    @pytest.mark.unit
    def test_rejects_risk_based_with_fixed_stop(self) -> None:
        """sizing_mode='risk_based' requires stop_type='atr'."""
        with pytest.raises(ValidationError) as exc_info:
            CreateComparisonRequest(
                **_cmp_kwargs(sizing_mode="risk_based", stop_type="fixed")
            )

        assert "sizing_mode='risk_based' requires stop_type='atr'" in str(
            exc_info.value
        )

    @pytest.mark.unit
    def test_accepts_risk_based_with_atr_stop(self) -> None:
        """Happy path: risk_based + atr stop should validate without error."""
        req = CreateComparisonRequest(
            **_cmp_kwargs(sizing_mode="risk_based", stop_type="atr")
        )

        assert req.sizing_mode == "risk_based"
        assert req.stop_type == "atr"

    @pytest.mark.unit
    def test_accepts_default_sizing_and_stop(self) -> None:
        """Default sizing_mode='fixed' with default stop_type='fixed' is valid."""
        req = CreateComparisonRequest(**_cmp_kwargs())

        assert req.sizing_mode == "fixed"
        assert req.stop_type == "fixed"

    @pytest.mark.unit
    def test_accepts_fixed_pct_sizing_mode(self) -> None:
        """sizing_mode='fixed_pct' on comparison requires position_size_pct."""
        req = CreateComparisonRequest(
            **_cmp_kwargs(sizing_mode="fixed_pct", position_size_pct=33.0)
        )

        assert req.sizing_mode == "fixed_pct"
        assert req.position_size_pct == 33.0

    @pytest.mark.unit
    def test_rejects_fixed_pct_without_position_size_pct(self) -> None:
        """sizing_mode='fixed_pct' on comparison requires position_size_pct."""
        with pytest.raises(ValidationError) as exc_info:
            CreateComparisonRequest(**_cmp_kwargs(sizing_mode="fixed_pct"))

        msg = str(exc_info.value)
        assert "fixed_pct" in msg
        assert "position_size_pct" in msg
