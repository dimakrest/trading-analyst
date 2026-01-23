"""Base Pydantic schemas with strict validation."""
from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    """Base model that forbids extra fields.

    All API request/response models should inherit from this class
    to ensure strict contract enforcement between frontend and backend.

    Usage:
        class MyRequest(StrictBaseModel):
            field: str

    When to use BaseModel instead:
        - Settings/config models that need extra="ignore" for env vars
        - Models parsing external data that may have extra fields
    """

    model_config = ConfigDict(extra="forbid")
