# Repository Layer

Async SQLAlchemy repository pattern for data access.

## Architecture

- **BaseRepository**: Generic CRUD operations
- **Type Safety**: Full type hints using generics
- **Async/Await**: SQLAlchemy 2.0 async support
- **Transaction**: Automatic rollback on errors

---

## Basic Usage

```python
from app.repositories import BaseRepository
from app.models.stock import StockPrice

async def get_stock_data(session: AsyncSession):
    repo = BaseRepository[StockPrice](StockPrice, session)

    # Create
    stock = await repo.create(symbol="AAPL", close_price=Decimal("152.50"))

    # Read
    retrieved = await repo.get_by_id(stock.id)

    # Update
    updated = await repo.update(stock.id, close_price=Decimal("160.00"))

    # List with filters
    stocks = await repo.list(filters={"symbol": "AAPL"}, limit=50)
```

---

## CRUD Operations

| Method | Description |
|--------|-------------|
| `create(**kwargs)` | Create entity |
| `get_by_id(id)` | Get by ID |
| `update(id, **kwargs)` | Update entity |
| `delete(id)` | Delete entity |
| `list(filters, limit)` | List with pagination |
| `count(filters)` | Count entities |
| `exists(**kwargs)` | Check existence |

---

## Error Handling

```python
from app.repositories import NotFoundError, DuplicateError, ValidationError

try:
    entity = await repo.create(**data)
except DuplicateError:
    # Handle duplicate
    pass
except ValidationError:
    # Handle validation failure
    pass
```

---

## Service Integration

```python
class StockService:
    def __init__(self, session: AsyncSession):
        self.repo = BaseRepository[StockPrice](StockPrice, session)

    async def get_latest(self, symbols: List[str]) -> List[StockPrice]:
        return await self.repo.list(filters={"symbol": symbols})
```

Pattern: **Controllers → Services → Repositories → Database**
