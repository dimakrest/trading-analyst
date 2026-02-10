# Phase 1 Type Checking Fixes - COMPLETE

## Summary

Fixed Pyright type checking errors in `DataService` that were reported after Phase 1 implementation of the DB session handling plan.

## Problem

After refactoring `DataService` to use `session_factory` instead of `session`, Pyright reported type errors at lines where `self._session_factory()` was called:

- Line 217: `async with self._session_factory() as session:` (cache check)
- Line 251: `async with self._session_factory() as session:` (double-check after lock)
- Line 288: `async with self._session_factory() as session:` (store + read)

Error message: `Object of type "None" cannot be called (reportOptionalCall)`

## Root Cause

The `self._session_factory` attribute is typed as:
```python
session_factory: Callable[[], AsyncContextManager[AsyncSession]] | None = None
```

While the code calls `self._require_session_factory()` at the start of `get_price_data()` which raises `RuntimeError` if `session_factory` is None, the type checker doesn't understand that this guarantees `self._session_factory` is not None for the rest of the function.

## Solution

Added a type assertion immediately after the `_require_session_factory()` call:

```python
async def get_price_data(...):
    self._require_session_factory()
    # Type assertion: After _require_session_factory(), we know it's not None
    assert self._session_factory is not None

    # ... rest of the method
```

This assertion:
1. Is purely for the type checker's benefit (does not affect runtime behavior)
2. Will always be true at runtime (since `_require_session_factory()` would have raised)
3. Tells Pyright that `self._session_factory` cannot be None for the rest of the function

## Verification

Before fix:
```bash
npx pyright backend/app/services/data_service.py
# 4 errors (3 type errors + 1 import error)
```

After fix:
```bash
npx pyright backend/app/services/data_service.py
# 1 error (only the import error, which is due to running locally without venv)
```

The import error (`reportMissingImports`) is expected when running pyright locally and will not occur in the Docker environment where dependencies are installed.

## Files Modified

1. `backend/app/services/data_service.py` - Added type assertion in `get_price_data()` method (line 203)

## Next Steps

Phase 1 is now complete with all type errors fixed. Ready to proceed to:
- Phase 2: Update Dependency Injection
- Phase 3: Update All Callers
- Phase 4: Update Tests
