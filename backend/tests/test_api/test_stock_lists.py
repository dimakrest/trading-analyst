"""Tests for Stock Lists API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock_list import StockList


class TestGetStockLists:
    """Tests for GET /api/v1/stock-lists."""

    @pytest.mark.asyncio
    async def test_get_lists_empty(self, async_client: AsyncClient):
        """Test getting lists when none exist.

        Arrange: Empty database
        Act: GET /api/v1/stock-lists
        Assert: Verify 200 status with empty list
        """
        response = await async_client.get("/api/v1/stock-lists")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_lists_with_data(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting lists with existing data.

        Arrange: Create stock lists in database
        Act: GET /api/v1/stock-lists
        Assert: Verify lists returned with correct structure
        """
        # Create stock lists directly in DB
        list1 = StockList(
            user_id=1,
            name="Tech Stocks",
            symbols=["AAPL", "GOOGL", "MSFT"],
        )
        list2 = StockList(
            user_id=1,
            name="Energy Stocks",
            symbols=["XOM", "CVX"],
        )
        db_session.add_all([list1, list2])
        await db_session.commit()

        response = await async_client.get("/api/v1/stock-lists")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["has_more"] is False

        # Verify sorted by name (Energy comes before Tech)
        assert data["items"][0]["name"] == "Energy Stocks"
        assert data["items"][1]["name"] == "Tech Stocks"

    @pytest.mark.asyncio
    async def test_get_lists_pagination(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test pagination of stock lists.

        Arrange: Create 5 stock lists
        Act: GET /api/v1/stock-lists?limit=2&offset=0
        Assert: Verify pagination works correctly
        """
        # Create 5 lists
        for i in range(5):
            stock_list = StockList(
                user_id=1,
                name=f"List {chr(65 + i)}",  # A, B, C, D, E
                symbols=["AAPL"],
            )
            db_session.add(stock_list)
        await db_session.commit()

        # Get first page
        response = await async_client.get("/api/v1/stock-lists?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["has_more"] is True
        assert data["items"][0]["name"] == "List A"
        assert data["items"][1]["name"] == "List B"

        # Get second page
        response = await async_client.get("/api/v1/stock-lists?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["has_more"] is True

        # Get last page
        response = await async_client.get("/api/v1/stock-lists?limit=2&offset=4")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 1
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_lists_only_own_user(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that only current user's lists are returned.

        Arrange: Create lists for user 1 and user 2
        Act: GET /api/v1/stock-lists (as user 1)
        Assert: Only user 1's lists returned
        """
        # Create lists for different users
        list_user1 = StockList(user_id=1, name="User 1 List", symbols=["AAPL"])
        list_user2 = StockList(user_id=2, name="User 2 List", symbols=["GOOGL"])
        db_session.add_all([list_user1, list_user2])
        await db_session.commit()

        response = await async_client.get("/api/v1/stock-lists")

        assert response.status_code == 200
        data = response.json()
        # Default user_id is 1 (from get_current_user_id dependency)
        assert data["total"] == 1
        assert data["items"][0]["name"] == "User 1 List"


class TestGetStockList:
    """Tests for GET /api/v1/stock-lists/{id}."""

    @pytest.mark.asyncio
    async def test_get_list_success(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test getting a specific list by ID.

        Arrange: Create a stock list
        Act: GET /api/v1/stock-lists/{id}
        Assert: Verify correct list returned
        """
        stock_list = StockList(
            user_id=1,
            name="My Watchlist",
            symbols=["AAPL", "GOOGL", "MSFT"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        response = await async_client.get(f"/api/v1/stock-lists/{stock_list.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == stock_list.id
        assert data["name"] == "My Watchlist"
        assert data["symbols"] == ["AAPL", "GOOGL", "MSFT"]
        assert data["symbol_count"] == 3

    @pytest.mark.asyncio
    async def test_get_list_not_found(self, async_client: AsyncClient):
        """Test getting a non-existent list.

        Arrange: Empty database
        Act: GET /api/v1/stock-lists/999
        Assert: Verify 404 status
        """
        response = await async_client.get("/api/v1/stock-lists/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_list_other_user(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that can't access another user's list.

        Arrange: Create a list for user 2
        Act: GET /api/v1/stock-lists/{id} (as user 1)
        Assert: Verify 404 status
        """
        stock_list = StockList(
            user_id=2,  # Different user
            name="Other User's List",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        response = await async_client.get(f"/api/v1/stock-lists/{stock_list.id}")

        assert response.status_code == 404


class TestCreateStockList:
    """Tests for POST /api/v1/stock-lists."""

    @pytest.mark.asyncio
    async def test_create_list_success(self, async_client: AsyncClient):
        """Test creating a new stock list.

        Arrange: Valid list data
        Act: POST /api/v1/stock-lists
        Assert: Verify 201 status and list created
        """
        payload = {
            "name": "Tech Giants",
            "symbols": ["AAPL", "GOOGL", "MSFT"],
        }

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Tech Giants"
        assert data["symbols"] == ["AAPL", "GOOGL", "MSFT"]
        assert data["symbol_count"] == 3
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_list_empty_symbols(self, async_client: AsyncClient):
        """Test creating a list with no symbols.

        Arrange: List with empty symbols
        Act: POST /api/v1/stock-lists
        Assert: Verify 201 status with empty list
        """
        payload = {"name": "Empty List", "symbols": []}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Empty List"
        assert data["symbols"] == []
        assert data["symbol_count"] == 0

    @pytest.mark.asyncio
    async def test_create_list_symbol_normalization(self, async_client: AsyncClient):
        """Test that symbols are normalized to uppercase.

        Arrange: List with lowercase symbols
        Act: POST /api/v1/stock-lists
        Assert: Verify symbols are uppercase
        """
        payload = {"name": "Mixed Case", "symbols": ["aapl", "Googl", "MSFT"]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["symbols"] == ["AAPL", "GOOGL", "MSFT"]

    @pytest.mark.asyncio
    async def test_create_list_deduplication(self, async_client: AsyncClient):
        """Test that duplicate symbols are removed.

        Arrange: List with duplicate symbols
        Act: POST /api/v1/stock-lists
        Assert: Verify duplicates removed, order preserved
        """
        payload = {
            "name": "With Dupes",
            "symbols": ["AAPL", "GOOGL", "aapl", "MSFT", "googl"],
        }

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 201
        data = response.json()
        # Should have unique symbols, preserving first occurrence order
        assert data["symbols"] == ["AAPL", "GOOGL", "MSFT"]
        assert data["symbol_count"] == 3

    @pytest.mark.asyncio
    async def test_create_list_duplicate_name(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test creating a list with duplicate name fails.

        Arrange: Existing list with same name
        Act: POST /api/v1/stock-lists
        Assert: Verify 400 status
        """
        # Create existing list
        existing = StockList(user_id=1, name="My List", symbols=["AAPL"])
        db_session.add(existing)
        await db_session.commit()

        payload = {"name": "My List", "symbols": ["GOOGL"]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_list_empty_name(self, async_client: AsyncClient):
        """Test creating a list with empty name fails.

        Arrange: Empty name
        Act: POST /api/v1/stock-lists
        Assert: Verify 422 validation error
        """
        payload = {"name": "", "symbols": ["AAPL"]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_list_name_too_long(self, async_client: AsyncClient):
        """Test creating a list with name too long fails.

        Arrange: Name > 100 characters
        Act: POST /api/v1/stock-lists
        Assert: Verify 422 validation error
        """
        payload = {"name": "A" * 101, "symbols": ["AAPL"]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_list_too_many_symbols(self, async_client: AsyncClient):
        """Test creating a list with too many symbols fails.

        Arrange: > 150 symbols
        Act: POST /api/v1/stock-lists
        Assert: Verify 422 validation error
        """
        payload = {"name": "Too Many", "symbols": [f"SYM{i}" for i in range(151)]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_list_whitespace_trimmed(self, async_client: AsyncClient):
        """Test that name and symbols are trimmed.

        Arrange: Name and symbols with whitespace
        Act: POST /api/v1/stock-lists
        Assert: Verify whitespace trimmed
        """
        payload = {"name": "  My List  ", "symbols": ["  AAPL  ", "  GOOGL  "]}

        response = await async_client.post("/api/v1/stock-lists", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My List"
        assert data["symbols"] == ["AAPL", "GOOGL"]


class TestUpdateStockList:
    """Tests for PUT /api/v1/stock-lists/{id}."""

    @pytest.mark.asyncio
    async def test_update_list_name(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating list name.

        Arrange: Create a list
        Act: PUT /api/v1/stock-lists/{id} with new name
        Assert: Verify name updated
        """
        stock_list = StockList(
            user_id=1,
            name="Original Name",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        payload = {"name": "New Name"}

        response = await async_client.put(
            f"/api/v1/stock-lists/{stock_list.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["symbols"] == ["AAPL"]  # Unchanged

    @pytest.mark.asyncio
    async def test_update_list_symbols(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating list symbols.

        Arrange: Create a list
        Act: PUT /api/v1/stock-lists/{id} with new symbols
        Assert: Verify symbols updated
        """
        stock_list = StockList(
            user_id=1,
            name="My List",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        payload = {"symbols": ["GOOGL", "MSFT"]}

        response = await async_client.put(
            f"/api/v1/stock-lists/{stock_list.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My List"  # Unchanged
        assert data["symbols"] == ["GOOGL", "MSFT"]
        assert data["symbol_count"] == 2

    @pytest.mark.asyncio
    async def test_update_list_both_fields(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating both name and symbols.

        Arrange: Create a list
        Act: PUT /api/v1/stock-lists/{id} with new name and symbols
        Assert: Verify both updated
        """
        stock_list = StockList(
            user_id=1,
            name="Original",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        payload = {"name": "Updated", "symbols": ["GOOGL", "MSFT"]}

        response = await async_client.put(
            f"/api/v1/stock-lists/{stock_list.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["symbols"] == ["GOOGL", "MSFT"]

    @pytest.mark.asyncio
    async def test_update_list_not_found(self, async_client: AsyncClient):
        """Test updating non-existent list.

        Arrange: Empty database
        Act: PUT /api/v1/stock-lists/999
        Assert: Verify 404 status
        """
        payload = {"name": "New Name"}

        response = await async_client.put("/api/v1/stock-lists/999", json=payload)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_list_duplicate_name(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating to duplicate name fails.

        Arrange: Create two lists
        Act: Update first list to have second list's name
        Assert: Verify 400 status
        """
        list1 = StockList(user_id=1, name="List 1", symbols=["AAPL"])
        list2 = StockList(user_id=1, name="List 2", symbols=["GOOGL"])
        db_session.add_all([list1, list2])
        await db_session.commit()
        await db_session.refresh(list1)

        payload = {"name": "List 2"}

        response = await async_client.put(
            f"/api/v1/stock-lists/{list1.id}", json=payload
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_list_same_name_ok(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test updating with same name succeeds.

        Arrange: Create a list
        Act: Update with same name (just updating symbols)
        Assert: Verify 200 status
        """
        stock_list = StockList(
            user_id=1,
            name="My List",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        # Update with same name but different symbols
        payload = {"name": "My List", "symbols": ["GOOGL"]}

        response = await async_client.put(
            f"/api/v1/stock-lists/{stock_list.id}", json=payload
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_list_symbol_normalization(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that updated symbols are normalized.

        Arrange: Create a list
        Act: Update with lowercase symbols
        Assert: Verify symbols are uppercase and deduplicated
        """
        stock_list = StockList(
            user_id=1,
            name="My List",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        payload = {"symbols": ["aapl", "googl", "AAPL"]}

        response = await async_client.put(
            f"/api/v1/stock-lists/{stock_list.id}", json=payload
        )

        assert response.status_code == 200
        data = response.json()
        assert data["symbols"] == ["AAPL", "GOOGL"]


class TestDeleteStockList:
    """Tests for DELETE /api/v1/stock-lists/{id}."""

    @pytest.mark.asyncio
    async def test_delete_list_success(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test deleting a list.

        Arrange: Create a list
        Act: DELETE /api/v1/stock-lists/{id}
        Assert: Verify 204 status and list no longer accessible
        """
        stock_list = StockList(
            user_id=1,
            name="To Delete",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)
        list_id = stock_list.id

        response = await async_client.delete(f"/api/v1/stock-lists/{list_id}")

        assert response.status_code == 204

        # Verify list is no longer accessible
        get_response = await async_client.get(f"/api/v1/stock-lists/{list_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_list_not_found(self, async_client: AsyncClient):
        """Test deleting non-existent list.

        Arrange: Empty database
        Act: DELETE /api/v1/stock-lists/999
        Assert: Verify 404 status
        """
        response = await async_client.delete("/api/v1/stock-lists/999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_list_other_user(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test can't delete another user's list.

        Arrange: Create list for user 2
        Act: DELETE /api/v1/stock-lists/{id} (as user 1)
        Assert: Verify 404 status
        """
        stock_list = StockList(
            user_id=2,  # Different user
            name="Other User's List",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)

        response = await async_client.delete(f"/api/v1/stock-lists/{stock_list.id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_soft_delete_preserves_data(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that delete is soft delete (data preserved).

        Arrange: Create a list
        Act: DELETE /api/v1/stock-lists/{id}
        Assert: Verify record exists but has deleted_at set
        """
        from sqlalchemy import select

        stock_list = StockList(
            user_id=1,
            name="To Soft Delete",
            symbols=["AAPL"],
        )
        db_session.add(stock_list)
        await db_session.commit()
        await db_session.refresh(stock_list)
        list_id = stock_list.id

        response = await async_client.delete(f"/api/v1/stock-lists/{list_id}")
        assert response.status_code == 204

        # Refresh session to see changes
        db_session.expire_all()

        # Query directly including soft-deleted records
        result = await db_session.execute(
            select(StockList).where(StockList.id == list_id)
        )
        deleted_list = result.scalar_one_or_none()

        assert deleted_list is not None
        assert deleted_list.deleted_at is not None
        assert deleted_list.name == "To Soft Delete"
