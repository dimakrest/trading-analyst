"""Base repository class providing generic CRUD operations with async support.

This module implements a generic repository pattern that provides common database
operations for all models. It includes error handling, transaction management,
type safety, and performance optimizations.
"""
import builtins
import logging
from datetime import datetime
from typing import Any
from typing import Generic
from typing import TypeVar

from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import Base

# Type variable for the model class
ModelType = TypeVar("ModelType", bound=Base)

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class DuplicateError(RepositoryError):
    """Raised when attempting to create a duplicate entity."""

    pass


class DatabaseError(RepositoryError):
    """Raised when a database operation fails."""

    pass


class BaseRepository(Generic[ModelType]):
    """Generic base repository providing common CRUD operations.

    This repository follows the async/await pattern and provides:
    - Type-safe CRUD operations
    - Transaction management
    - Error handling and logging
    - Query optimization
    - Pagination support
    - Bulk operations

    Example:
        ```python
        class StockPriceRepository(BaseRepository[StockPrice]):
            def __init__(self, session: AsyncSession):
                super().__init__(StockPrice, session)

        # Usage
        repo = StockPriceRepository(session)
        stock_price = await repo.get_by_id(1)
        ```
    """

    def __init__(self, model: type[ModelType], session: AsyncSession):
        """Initialize repository with model class and database session.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session
        self.logger = logging.getLogger(f"{__name__}.{model.__name__}Repository")

    async def get_by_id(
        self, id: int, include_deleted: bool = False, load_relationships: list[str] = None
    ) -> ModelType | None:
        """Retrieve a single entity by its ID.

        Args:
            id: Primary key value
            include_deleted: Whether to include soft-deleted records
            load_relationships: List of relationship names to eagerly load

        Returns:
            Model instance or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model).where(self.model.id == id)

            # Handle soft delete filtering
            if not include_deleted and hasattr(self.model, "deleted_at"):
                query = query.where(self.model.deleted_at.is_(None))

            # Add eager loading for relationships
            if load_relationships:
                for rel in load_relationships:
                    if hasattr(self.model, rel):
                        query = query.options(selectinload(getattr(self.model, rel)))

            result = await self.session.execute(query)
            entity = result.scalar_one_or_none()

            if entity:
                self.logger.debug(f"Retrieved {self.model.__name__} with id={id}")
            else:
                self.logger.debug(f"No {self.model.__name__} found with id={id}")

            return entity

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to get {self.model.__name__} by id {id}: {e}")
            raise DatabaseError(f"Database error retrieving {self.model.__name__}: {str(e)}")

    async def create(self, **kwargs) -> ModelType:
        """Create a new entity.

        Args:
            **kwargs: Field values for the new entity

        Returns:
            Created model instance

        Raises:
            DuplicateError: If entity already exists (unique constraint violation)
            ValidationError: If data validation fails
            DatabaseError: If database operation fails
        """
        try:
            entity = self.model(**kwargs)
            self.session.add(entity)
            await self.session.flush()  # Get the ID without committing
            await self.session.refresh(entity)  # Refresh to get generated fields

            self.logger.info(f"Created {self.model.__name__} with id={entity.id}")
            return entity

        except IntegrityError as e:
            await self.session.rollback()
            self.logger.warning(f"Integrity error creating {self.model.__name__}: {e}")
            raise DuplicateError(f"Entity already exists: {str(e)}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed to create {self.model.__name__}: {e}")
            raise DatabaseError(f"Database error creating {self.model.__name__}: {str(e)}")

    async def create_many(self, entities_data: list[dict[str, Any]]) -> list[ModelType]:
        """Create multiple entities in a single transaction.

        Args:
            entities_data: List of dictionaries containing field values

        Returns:
            List of created model instances

        Raises:
            DuplicateError: If any entity already exists
            ValidationError: If data validation fails
            DatabaseError: If database operation fails
        """
        if not entities_data:
            return []

        try:
            entities = [self.model(**data) for data in entities_data]
            self.session.add_all(entities)
            await self.session.flush()

            # Refresh all entities to get generated fields
            for entity in entities:
                await self.session.refresh(entity)

            self.logger.info(f"Created {len(entities)} {self.model.__name__} records")
            return entities

        except IntegrityError as e:
            await self.session.rollback()
            self.logger.warning(f"Integrity error creating {self.model.__name__} batch: {e}")
            raise DuplicateError(f"Duplicate entities in batch: {str(e)}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed to create {self.model.__name__} batch: {e}")
            raise DatabaseError(f"Database error creating {self.model.__name__} batch: {str(e)}")

    async def update(self, id: int, **kwargs) -> ModelType | None:
        """Update an existing entity by ID.

        Args:
            id: Primary key value
            **kwargs: Field values to update

        Returns:
            Updated model instance or None if not found

        Raises:
            DuplicateError: If update violates unique constraints
            ValidationError: If data validation fails
            DatabaseError: If database operation fails
        """
        try:
            # First, get the entity
            entity = await self.get_by_id(id)
            if not entity:
                self.logger.warning(f"No {self.model.__name__} found with id={id} for update")
                return None

            # Update fields
            for key, value in kwargs.items():
                if hasattr(entity, key) and key not in ("id", "created_at"):
                    setattr(entity, key, value)

            # Update the updated_at timestamp if it exists
            if hasattr(entity, "updated_at"):
                entity.updated_at = datetime.utcnow()

            await self.session.flush()
            await self.session.refresh(entity)

            self.logger.info(f"Updated {self.model.__name__} with id={id}")
            return entity

        except IntegrityError as e:
            await self.session.rollback()
            self.logger.warning(f"Integrity error updating {self.model.__name__} id={id}: {e}")
            raise DuplicateError(f"Update violates constraints: {str(e)}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed to update {self.model.__name__} id={id}: {e}")
            raise DatabaseError(f"Database error updating {self.model.__name__}: {str(e)}")

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        order_by: str | None = None,
        order_desc: bool = False,
        filters: dict[str, Any] | None = None,
    ) -> list[ModelType]:
        """List entities with pagination and filtering.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Whether to include soft-deleted records
            order_by: Field name to order by (default: id)
            order_desc: Whether to order in descending order
            filters: Dictionary of field filters

        Returns:
            List of model instances

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model)

            # Apply soft delete filtering
            if not include_deleted and hasattr(self.model, "deleted_at"):
                query = query.where(self.model.deleted_at.is_(None))

            # Apply custom filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        column = getattr(self.model, field)
                        if isinstance(value, list):
                            query = query.where(column.in_(value))
                        elif isinstance(value, dict) and "operator" in value:
                            # Support for complex filters like {'operator': 'gte', 'value': 100}
                            op = value["operator"]
                            val = value["value"]
                            if op == "gte":
                                query = query.where(column >= val)
                            elif op == "lte":
                                query = query.where(column <= val)
                            elif op == "gt":
                                query = query.where(column > val)
                            elif op == "lt":
                                query = query.where(column < val)
                            elif op == "like":
                                query = query.where(column.like(f"%{val}%"))
                        else:
                            query = query.where(column == value)

            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                if order_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            else:
                # Default ordering by id
                if order_desc:
                    query = query.order_by(desc(self.model.id))
                else:
                    query = query.order_by(asc(self.model.id))

            # Apply pagination
            query = query.offset(offset).limit(limit)

            result = await self.session.execute(query)
            entities = result.scalars().all()

            self.logger.debug(
                f"Listed {len(entities)} {self.model.__name__} records "
                f"(offset={offset}, limit={limit})"
            )
            return list(entities)

        except SQLAlchemyError as e:
            self.logger.error(f"Failed to list {self.model.__name__}: {e}")
            raise DatabaseError(f"Database error listing {self.model.__name__}: {str(e)}")

    async def get_or_create(
        self, defaults: dict[str, Any] | None = None, **kwargs
    ) -> tuple[ModelType, bool]:
        """Get an existing entity or create a new one.

        Args:
            defaults: Default values to use when creating a new entity
            **kwargs: Field criteria to search for existing entity

        Returns:
            Tuple of (entity, created) where created is True if entity was created

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Try to get existing entity
            query = select(self.model)
            for field, value in kwargs.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

            # Don't include soft-deleted records
            if hasattr(self.model, "deleted_at"):
                query = query.where(self.model.deleted_at.is_(None))

            result = await self.session.execute(query)
            entity = result.scalar_one_or_none()

            if entity:
                self.logger.debug(f"Found existing {self.model.__name__}")
                return entity, False

            # Create new entity
            create_data = kwargs.copy()
            if defaults:
                create_data.update(defaults)

            entity = await self.create(**create_data)
            self.logger.info(f"Created new {self.model.__name__} with id={entity.id}")
            return entity, True

        except SQLAlchemyError as e:
            self.logger.error(f"Failed get_or_create for {self.model.__name__}: {e}")
            raise DatabaseError(
                f"Database error in get_or_create for {self.model.__name__}: {str(e)}"
            )

    async def bulk_upsert(
        self,
        data: builtins.list[dict[str, Any]],
        conflict_fields: builtins.list[str],
        update_fields: builtins.list[str] | None = None,
    ) -> int:
        """Perform bulk upsert (insert or update on conflict).

        Note: This method uses row-by-row application logic which is inefficient.
        For PostgreSQL, prefer using repository-specific upsert methods that
        leverage native INSERT ... ON CONFLICT DO UPDATE syntax.

        Args:
            data: List of dictionaries containing entity data
            conflict_fields: Fields that define uniqueness for conflict detection
            update_fields: Fields to update on conflict (if None, update all except conflict fields)

        Returns:
            Number of affected rows

        Raises:
            DatabaseError: If database operation fails
        """
        if not data:
            return 0

        try:
            # For PostgreSQL, we can use ON CONFLICT
            # This is a simplified implementation - in production you might want
            # to use PostgreSQL-specific features or handle different databases

            affected_rows = 0

            for item_data in data:
                # Check if entity exists
                conflict_criteria = {
                    field: item_data[field] for field in conflict_fields if field in item_data
                }
                entity, created = await self.get_or_create(defaults=item_data, **conflict_criteria)

                if not created and update_fields:
                    # Update existing entity
                    update_data = {
                        field: item_data[field] for field in update_fields if field in item_data
                    }
                    if update_data:
                        updated_entity = await self.update(entity.id, **update_data)
                        if updated_entity:
                            affected_rows += 1
                else:
                    affected_rows += 1

            self.logger.info(f"Bulk upserted {affected_rows} {self.model.__name__} records")
            return affected_rows

        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed bulk upsert for {self.model.__name__}: {e}")
            raise DatabaseError(
                f"Database error in bulk upsert for {self.model.__name__}: {str(e)}"
            )

    async def delete_batch(
        self, filters: dict[str, Any], soft_delete: bool = True, limit: int | None = None
    ) -> int:
        """Delete multiple entities based on filters.

        Args:
            filters: Dictionary of field filters
            soft_delete: Whether to soft delete (if supported) or hard delete
            limit: Maximum number of entities to delete

        Returns:
            Number of deleted entities

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            query = select(self.model)

            # Apply filters
            for field, value in filters.items():
                if hasattr(self.model, field):
                    column = getattr(self.model, field)
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                    else:
                        query = query.where(column == value)

            # Apply limit
            if limit:
                query = query.limit(limit)

            # Get entities to delete
            result = await self.session.execute(query)
            entities = result.scalars().all()

            if not entities:
                return 0

            deleted_count = 0

            if soft_delete and hasattr(self.model, "soft_delete"):
                # Soft delete
                for entity in entities:
                    entity.soft_delete()
                    deleted_count += 1
            else:
                # Hard delete
                for entity in entities:
                    await self.session.delete(entity)
                    deleted_count += 1

            await self.session.flush()

            self.logger.info(f"Deleted {deleted_count} {self.model.__name__} records")
            return deleted_count

        except SQLAlchemyError as e:
            await self.session.rollback()
            self.logger.error(f"Failed batch delete for {self.model.__name__}: {e}")
            raise DatabaseError(
                f"Database error in batch delete for {self.model.__name__}: {str(e)}"
            )
