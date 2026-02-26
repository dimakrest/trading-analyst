"""Stock List model for user-created symbol collections."""

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockList(Base):
    """User's personal stock list.

    Stores a named collection of stock symbols for quick access
    in the Stock Analysis page.
    """

    __tablename__ = "stock_lists"

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        doc="User who owns this list"
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Display name for the list"
    )

    symbols: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)),
        nullable=False,
        default=list,
        doc="List of stock ticker symbols"
    )
