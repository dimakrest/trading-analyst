"""Schemas for Agent Config API."""

from typing import Literal

from pydantic import Field

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


class AgentConfigUpdate(StrictBaseModel):
    """Request to update an agent configuration."""

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


class AgentConfigResponse(StrictBaseModel):
    """Response containing an agent configuration."""

    id: int
    name: str
    agent_type: str
    scoring_algorithm: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Default CCI",
                    "agent_type": "live20",
                    "scoring_algorithm": "cci"
                },
                {
                    "id": 2,
                    "name": "RSI-2 Strategy",
                    "agent_type": "live20",
                    "scoring_algorithm": "rsi2"
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
                            "scoring_algorithm": "cci"
                        },
                        {
                            "id": 2,
                            "name": "RSI-2 Strategy",
                            "agent_type": "live20",
                            "scoring_algorithm": "rsi2"
                        }
                    ],
                    "total": 2
                }
            ]
        }
    }
