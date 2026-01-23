"""Base model class with common fields for all database models.
"""
from datetime import UTC
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models.

    Provides common fields and functionality that all models should have:
    - Primary key ID
    - Created and updated timestamps
    - Optional soft delete functionality
    """

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Timestamps with timezone awareness
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Timestamp when the record was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        doc="Timestamp when the record was last updated",
    )

    # Optional soft delete field
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Timestamp when the record was soft-deleted (null if active)",
    )

    # Optional notes field for debugging/auditing
    notes: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, doc="Optional notes or comments about this record"
    )

    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted without removing it from the database."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None

    def to_dict(self) -> dict:
        """Convert the model instance to a dictionary.

        Returns:
            dict: Dictionary representation of the model
        """
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            # Convert datetime to ISO format for JSON serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    @classmethod
    def get_table_name(cls) -> str:
        """Get the table name for this model."""
        return cls.__tablename__

    def update_from_dict(self, data: dict) -> None:
        """Update model fields from a dictionary.

        Args:
            data: Dictionary containing field values to update
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ("id", "created_at"):
                setattr(self, key, value)


# Common mixins for specific functionality


class TimestampMixin:
    """Mixin for models that only need timestamp functionality."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Mixin for models that need soft delete functionality."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
