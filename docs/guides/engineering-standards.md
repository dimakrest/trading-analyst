# Engineering Standards

Code quality requirements for Trading Analyst. This document serves both frontend and backend agents.

---

## 1. Core Principles

### What Constitutes Good Code

Good code is:
- **Functional** - Does what it's supposed to do
- **Understandable** - Clear to read and reason about
- **Maintainable** - Easy to change and extend

### Pyramid of Coding Principles

Apply in this order (most important first):

```
                    △
                   /  \
                  / BS \      ← Boy Scout Rule (leave it better)
                 /------\
                /  Clean \    ← Clean Code (readable, simple)
               /   Code   \
              /------------\
             /     DRY      \  ← Don't Repeat Yourself
            /----------------\
           /       KISS       \ ← Keep It Simple, Stupid
          /--------------------\
         /        YAGNI         \ ← You Aren't Gonna Need It
        /________________________\
```

1. **YAGNI** - Don't build features until you need them
2. **KISS** - Choose the simplest solution that works
3. **DRY** - Extract only when you see actual repetition (3+ times)
4. **Clean Code** - Make code readable and self-documenting
5. **Boy Scout Rule** - Leave code better than you found it

### SOLID Principles

| Principle | Summary |
|-----------|---------|
| **S** - Single Responsibility | A class/module should have one reason to change |
| **O** - Open/Closed | Open for extension, closed for modification |
| **L** - Liskov Substitution | Subtypes must be substitutable for their base types |
| **I** - Interface Segregation | Many specific interfaces beat one general-purpose interface |
| **D** - Dependency Inversion | Depend on abstractions, not concretions |

---

## 2. Clean Code Guidelines

### Naming

- **Short but meaningful** - Balance brevity with clarity
- **Pronounceable** - You should be able to say it out loud
- **Searchable** - Avoid single letters except for loop counters
- **Nouns for classes** - `StockService`, `PriceData`, `TradeRepository`
- **Verbs for functions** - `fetch_prices()`, `validate_setup()`, `calculate_risk()`

```python
# ✅ Good
def fetch_stock_prices(symbol: str) -> pd.DataFrame: ...
class TradeExecutor: ...

# ❌ Bad
def getData(s): ...  # Vague, abbreviated
class Mgr: ...       # Cryptic abbreviation
```

### Functions

- **Small** - Do one thing well
- **Single responsibility** - If you need "and" to describe it, split it
- **No side effects** - Or make them explicit in the name
- **Max 3 arguments** - More suggests the function does too much

```python
# ✅ Good: Clear, focused functions
def get_symbol_info(symbol: str) -> SymbolInfo: ...
def fetch_prices(symbol: str, period: str) -> pd.DataFrame: ...
def calculate_moving_average(prices: pd.Series, window: int) -> pd.Series: ...

# ❌ Bad: Function doing too much
def process_stock(symbol, period, calculate_ma, send_alert, update_db): ...
```

### Avoid

- **Magic numbers** - Use named constants from config
- **Dead code** - Delete it, git remembers
- **Negative conditionals** - `if is_valid:` not `if not is_invalid:`
- **Long switch/if-else chains** - Use polymorphism or lookup tables

---

## 3. Error Handling

### Principles

- **Never return null** - Use exceptions or empty collections
- **Never pass null** - Functions shouldn't accept null parameters
- **Exceptions over error codes** - More explicit, can't be ignored
- **Informative exceptions** - Include operation + failure reason
- **Inform users** - Unrecoverable errors should have clear messages

```python
# ✅ Required: Handle specific exceptions
try:
    data = await service.fetch_stock_data(symbol)
except InvalidSymbolError as e:
    logger.warning(f"Invalid symbol {symbol}: {e}")
    return []
except Exception as e:
    logger.error(f"Data fetching failed: {e}")
    raise

# ❌ Forbidden: Bare except
try:
    data = service.fetch_stock_data(symbol)
except:
    return None  # Swallows all errors, masks bugs
```

---

## 4. Comments Policy

### Express Intent Through Code

Comments are a last resort. If you need a comment, first try to:
1. Rename the variable/function to be clearer
2. Extract a well-named function
3. Simplify the logic

### When Comments Are Appropriate

- **Explaining intent** - Why, not what (the code shows what)
- **Warning of consequences** - "Don't change this order, it affects X"
- **Amplifying importance** - "This timeout is critical for avoiding rate limits"

### Always Delete

- Commented-out code (git has history)
- Redundant comments that repeat the code
- Outdated comments that no longer match the code

```python
# ❌ Bad: Explains what (obvious from code)
# Increment counter by 1
counter += 1

# ✅ Good: Explains why (not obvious)
# Yahoo Finance rate limits after 2000 requests/hour
await asyncio.sleep(1.8)
```

---

## 5. Logging & Security

### Logging Standards

- **Structured JSON logging** with context (request_id, timestamp)
- **Log all warnings, errors, exceptions** with stack traces
- **Never log sensitive data** - API keys, passwords, PII

```python
# ✅ Good: Structured with context
logger.info("Fetching stock data", extra={
    "symbol": symbol,
    "period": period,
    "request_id": request_id
})

# ❌ Bad: Unstructured, contains sensitive data
logger.info(f"Fetching {symbol} with api_key={api_key}")
```

### Security Rules

- **No secrets in code** - Use environment variables
- **No credentials in logs** - Mask sensitive data
- **No API keys in git** - Use .env files (gitignored)

---

## 6. Language-Specific Standards

### Python (Backend)

#### Type Hints (Required)

```python
# ✅ Required: All functions must have type hints
from typing import Optional
import pandas as pd

def fetch_stock_data(
    symbol: str,
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> pd.DataFrame:
    """Fetch stock data with full type hints."""
    pass

# ❌ Forbidden: Missing type hints
def fetch_stock_data(symbol, start_date, end_date=None):
    pass
```

#### Service Layer Pattern

```python
# ✅ Required: Follow established pattern
# API controllers → Services → Repositories

# In api/stocks.py
@router.get("/prices")
async def get_stock_prices(symbol: str, period: str):
    return await stock_service.get_prices(symbol, period)

# In services/stock_service.py
class StockService:
    async def get_prices(self, symbol: str, period: str):
        data = await self.data_repo.fetch(symbol, period)
        return self.format_prices(data)
```

#### Pydantic Strict Validation (Required)

**CRITICAL**: All API request/response models MUST use strict validation.

```python
# ✅ Required: Inherit from StrictBaseModel for API models
from app.schemas.base import StrictBaseModel

class MyRequest(StrictBaseModel):
    """Request model - extra fields will be rejected with 422."""
    field: str

class MyResponse(StrictBaseModel):
    """Response model - enforces API contract."""
    data: str
```

**Why This Matters**:
- Without `extra="forbid"`, Pydantic silently ignores extra fields
- A typo like `trigger_pricee` would be silently dropped
- Strict validation catches errors immediately with 422 response

**When to Use `StrictBaseModel`**:
- All API request/response models

**When to Use Regular `BaseModel`**:
- Settings/config (needs `extra="ignore"` for env vars)
- External API responses (may have extra fields)
- Internal DTOs not exposed via API

#### Configuration

```python
# ✅ Required: Use centralized config
from app.config import settings

ma_period = settings.MA_SHORT_PERIOD
confidence = settings.MIN_CONFIDENCE

# ❌ Forbidden: Hardcoded values
ma_period = 50  # Magic number
confidence = 0.6  # Hardcoded
```

#### Tools

```bash
# Format code
black backend/app/

# Type checking
mypy backend/app/

# Run tests with coverage
pytest --cov=app --cov-report=html
```

### TypeScript (Frontend)

#### Strict TypeScript (Required)

- Strict mode enabled in tsconfig
- No `any` types without explicit justification
- Proper type definitions for all components and functions

#### Tools

```bash
# Format and lint
npm run format
npm run lint
npm run type-check

# Tests
npm test
```

---

## 7. API Standards

### URL Naming

```python
# ✅ Required: Use kebab-case for multi-word URLs
router = APIRouter(prefix="/live-20")           # kebab-case
router = APIRouter(prefix="/stock-lists")       # kebab-case

# ❌ Forbidden: snake_case in URLs
router = APIRouter(prefix="/stock_lists")       # snake_case
```

```python
# ✅ Required: Use plural nouns for resource collections
@router.get("/recommendations")      # Plural for collections
@router.get("/stocks/{symbol}")      # Plural collection, singular parameter

# ❌ Forbidden: Singular nouns for collections
@router.get("/recommendation")       # Should be plural
```

```python
# ✅ Allowed: Action verbs for non-CRUD operations (POST endpoints)
@router.post("/analyze")             # Action endpoint
@router.post("/validate")            # Action endpoint
```

### HTTP Status Codes

```python
# Success Codes
200  # OK - Standard success for GET/POST returning data synchronously
201  # Created - Resource was created
202  # Accepted - Request accepted for async processing (returns job ID)
204  # No Content - Success with no body (e.g., DELETE)

# Client Error Codes
400  # Bad Request - Invalid input
404  # Not Found - Resource doesn't exist
422  # Unprocessable Entity - Validation error (Pydantic default)

# Server Error Codes
500  # Internal Server Error - Unexpected errors
503  # Service Unavailable - External service down
504  # Gateway Timeout - External service timeout
```

**Important**: Only use 202 if the request truly runs asynchronously (returns immediately with job ID, client polls). If it waits and returns results, use 200.

### Pagination

All paginated endpoints MUST use consistent structure:

```python
# ✅ Required: Standard pagination response
class PaginatedResponse(StrictBaseModel):
    items: list[ItemType]    # Always use 'items' as the key
    total: int               # Total count matching filters
    has_more: bool           # Whether more items exist
    limit: int               # Actual limit used
    offset: int              # Actual offset used

# ✅ Required: Standard pagination query parameters
@router.get("/items")
async def list_items(
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Items to skip"),
):
    items = await repo.get_items(limit=limit, offset=offset)
    total = await repo.count_items()
    return {
        "items": items,
        "total": total,
        "has_more": (offset + len(items)) < total,
        "limit": limit,
        "offset": offset,
    }

# ❌ Forbidden: Inconsistent pagination keys
return {"runs": runs, "total": total}      # Use 'items', not 'runs'
```

### API Documentation (Required)

```python
# ✅ Required: Complete endpoint documentation
@router.get(
    "/{symbol}/prices",
    response_model=StockDataResponse,
    summary="Get Stock Prices",
    description="Retrieve historical OHLCV price data for a symbol.",
    operation_id="get_stock_prices",
    responses={
        400: {"description": "Invalid symbol or date range"},
        404: {"description": "Symbol not found"},
    }
)

# ❌ Forbidden: Missing documentation
@router.get("/{symbol}/prices")
async def get_stock_prices(symbol: str):
    pass
```

All Pydantic schemas MUST have field descriptions:

```python
# ✅ Required: Complete schema documentation
class PriceData(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    close: float = Field(..., description="Closing price")

    model_config = {"json_schema_extra": {"examples": [...]}}

# ❌ Forbidden: Missing descriptions
class PriceData(BaseModel):
    date: str
    close: float
```

### Response Structure

```python
# ✅ Required: Direct data responses (no envelope)
@router.get("/items/{id}")
async def get_item(id: int) -> ItemResponse:
    return item  # Direct response, not {"data": item}

# ✅ Required: Errors via HTTPException
raise HTTPException(status_code=404, detail="Item not found")
# Returns: {"detail": "Item not found"}
```

---

## 10. Forbidden Practices

**Never:**
1. Commit secrets or API keys
2. Use bare `except:` clauses
3. Hardcode configuration values
4. Skip type hints on functions
5. Write code without tests
6. Ignore existing patterns in codebase
7. Create API endpoints without documentation
8. Create Pydantic schemas without field descriptions
9. Use `BaseModel` directly for API request/response models (use `StrictBaseModel`)
10. Use snake_case in URL paths (use kebab-case)
11. Use inconsistent pagination keys (always use `items`)
12. Use 202 ACCEPTED for synchronous operations
13. Return or pass null - use exceptions or empty values
14. Leave commented-out code
15. Add comments that explain "what" instead of "why"

---

Keep it simple. These standards focus on what's essential for maintainable, reliable code.
