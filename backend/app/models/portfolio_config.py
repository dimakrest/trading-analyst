"""Portfolio configuration model for named portfolio selection presets."""
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PortfolioConfig(Base):
    """Named portfolio configuration preset.

    Stores reusable portfolio selection settings that can be selected
    when creating Arena simulations.
    """

    __tablename__ = "portfolio_configs"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        doc="User-provided name (e.g., 'Conservative Sector Caps')",
    )
    portfolio_strategy: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="none",
        doc="Portfolio selector strategy key",
    )
    position_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        doc="Per-position dollar allocation used for simulations",
    )
    min_buy_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        doc="Minimum score required for BUY decisions",
    )
    trailing_stop_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
        doc="Trailing stop percentage used for simulations",
    )
    max_per_sector: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Max concurrent positions per sector (null = unlimited)",
    )
    max_open_positions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Max total open positions (null = unlimited)",
    )
