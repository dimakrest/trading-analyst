# Review: Improve DB Session Handling

**Status**: ✅ APPROVED (with minor notes)

This is a **high-quality, technically sound plan** that correctly addresses the connection pool exhaustion issue by narrowing the scope of database sessions. The analysis of `expire_on_commit=False` and detached object state is correct and critical for this approach.

## 1. Completeness & Technical Soundness
The plan is comprehensive and technically accurate.
- **Session Lifecycle**: Switching to `session_factory` and using short-lived sessions around specific DB ops (check/store) while leaving the API call session-free is the correct pattern.
- **Detached Objects**: Verified that `StockPrice` model (checked in `backend/app/models/stock.py`) consists of scalar columns (`open_price`, `high_price`, etc.) and no lazy-loaded relationships. Accessing these on detached objects with `expire_on_commit=False` is safe.
- **Locking**: The `asyncio.Lock` strategy (`fetch_lock`) correctly persists across the session boundaries to prevent thundering herds.

## 2. Implementation & Dependencies
- **Imports**: `DataService` will now instantiate `StockPriceRepository` and `MarketDataCache` internally. Verified that these classes are already imported in `data_service.py`.
- **Dependency Injection**: The updates to `deps.py` correctly simplify `get_data_service` to inject the factory instead of constructing the full dependency tree.

## 3. Testing Strategy
The proposed testing approach (Patching `StockPriceRepository`/`MarketDataCache` classes) is the correct way to unit test `DataService` now that it manages its own dependencies.
- **Recommendation**: Ensure integration tests (using real DB) cover the "cache miss -> fetch -> store -> read" cycle to verify the transaction commit boundaries work as expected (i.e., data stored in one short session is visible in the immediate next short session).

## 4. Risks & Edge Cases
- **Transaction Isolation**: Note that "Check Cache" and "Store Result" are now in separate transactions. This is acceptable for this use case (cache consistency doesn't require strict serializability with the fetch).
- **Future-Proofing**: If `StockPrice` ever adds lazy-loaded relationships (e.g., to a `Stock` metadata table), accessing them on detached objects would fail. This is a low risk now but worth noting for future schema changes.

## 5. Action Items
Proceed with the implementation as planned.
1. **Refactor `DataService`** (Phase 1)
2. **Update `deps.py`** (Phase 2)
3. **Update Callers** (Phase 3) - Crucial to do immediately to fix build.
4. **Update Tests** (Phase 4) - Expect significant churn in `test_data_service.py`.

No critical blockers found.
