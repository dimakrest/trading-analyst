"""Schemas for Agent Config API."""

from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import StrictBaseModel


class AgentConfigCreate(StrictBaseModel):
    """Request to create a new agent configuration."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for the agent configuration"
    )
    agent_type: Literal["live20"] = Field(
        default="live20",
        description="Agent type (currently only 'live20' is supported)"
    )
    scoring_algorithm: Literal["cci", "rsi2"] = Field(
        default="cci",
        description="Scoring algorithm for momentum criterion"
    )
    volume_score: int = Field(
        default=25,
        ge=0,
        le=100,
        description="Score weight for volume signal"
    )
    candle_pattern_score: int = Field(
        default=25,
        ge=0,
        le=100,
        description="Score weight for candle pattern signal"
    )
    cci_score: int = Field(
        default=25,
        ge=0,
        le=100,
        description="Score weight for momentum signal (CCI/RSI-2)"
    )
    ma20_distance_score: int = Field(
        default=25,
        ge=0,
        le=100,
        description="Score weight for MA20 distance signal"
    )

    @model_validator(mode="after")
    def validate_score_total(self) -> "AgentConfigCreate":
        """Validate configured signal score weights sum to 100."""
        total = (
            self.volume_score
            + self.candle_pattern_score
            + self.cci_score
            + self.ma20_distance_score
        )
        if total != 100:
            raise ValueError(
                "Signal scores must sum to 100 "
                f"(got {total}: volume={self.volume_score}, candle={self.candle_pattern_score}, "
                f"cci={self.cci_score}, ma20={self.ma20_distance_score})"
            )
        return self


class AgentConfigUpdate(StrictBaseModel):
    """Request to update an agent configuration.

    Note: Signal score weights are validated as a group. Omitted scores keep
    their current values, but the resulting total (existing + provided) must
    still equal 100. To change one score, send all four scores in the request.
    """

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="New display name"
    )
    scoring_algorithm: Literal["cci", "rsi2"] | None = Field(
        None,
        description="New scoring algorithm"
    )
    volume_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="New score weight for volume signal (all 4 scores must sum to 100)"
    )
    candle_pattern_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="New score weight for candle pattern signal (all 4 scores must sum to 100)"
    )
    cci_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="New score weight for momentum signal (all 4 scores must sum to 100)"
    )
    ma20_distance_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="New score weight for MA20 distance signal (all 4 scores must sum to 100)"
    )


class AgentConfigResponse(StrictBaseModel):
    """Response containing an agent configuration."""

    id: int
    name: str
    agent_type: str
    scoring_algorithm: str
    volume_score: int
    candle_pattern_score: int
    cci_score: int
    ma20_distance_score: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Default CCI",
                    "agent_type": "live20",
                    "scoring_algorithm": "cci",
                    "volume_score": 25,
                    "candle_pattern_score": 25,
                    "cci_score": 25,
                    "ma20_distance_score": 25
                },
                {
                    "id": 2,
                    "name": "RSI-2 Strategy",
                    "agent_type": "live20",
                    "scoring_algorithm": "rsi2",
                    "volume_score": 20,
                    "candle_pattern_score": 30,
                    "cci_score": 30,
                    "ma20_distance_score": 20
                }
            ]
        }
    }


class AgentConfigListResponse(StrictBaseModel):
    """Response containing a list of agent configurations."""

    items: list[AgentConfigResponse]
    total: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": 1,
                            "name": "Default CCI",
                            "agent_type": "live20",
                            "scoring_algorithm": "cci",
                            "volume_score": 25,
                            "candle_pattern_score": 25,
                            "cci_score": 25,
                            "ma20_distance_score": 25
                        },
                        {
                            "id": 2,
                            "name": "RSI-2 Strategy",
                            "agent_type": "live20",
                            "scoring_algorithm": "rsi2",
                            "volume_score": 20,
                            "candle_pattern_score": 30,
                            "cci_score": 30,
                            "ma20_distance_score": 20
                        }
                    ],
                    "total": 2
                }
            ]
        }
    }
