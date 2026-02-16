"""Agent configuration model for named scoring presets."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentConfig(Base):
    """Named agent configuration preset.

    Stores reusable agent settings that can be selected when running
    Live20 evaluations or Arena simulations.
    """

    __tablename__ = "agent_configs"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True,
        doc="User-provided name (e.g., 'RSI-2 Aggressive')"
    )
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="live20",
        doc="Agent type: 'live20' (only option for now)"
    )
    scoring_algorithm: Mapped[str] = mapped_column(
        String(20), nullable=False, default="cci",
        doc="Scoring algorithm: 'cci' or 'rsi2'"
    )
