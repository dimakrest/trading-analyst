import { useState, useEffect, useCallback } from 'react';
import {
  stockListService,
  type StockList,
  type CreateStockListRequest,
  type UpdateStockListRequest,
} from '../services/stockListService';

/**
 * Result interface for the useStockLists hook
 */
interface UseStockListsResult {
  /** Array of stock lists */
  lists: StockList[];
  /** Whether the initial load is in progress */
  isLoading: boolean;
  /** Error message if any operation failed */
  error: string | null;
  /** Create a new stock list */
  createList: (data: CreateStockListRequest) => Promise<StockList>;
  /** Update an existing stock list */
  updateList: (id: number, data: UpdateStockListRequest) => Promise<StockList>;
  /** Delete a stock list */
  deleteList: (id: number) => Promise<void>;
  /** Refetch all lists from the server */
  refetch: () => Promise<void>;
}

/**
 * Custom hook for managing stock lists
 *
 * Provides CRUD operations with optimistic local state updates
 * and automatic sorting by name.
 *
 * @returns UseStockListsResult with lists data and CRUD operations
 *
 * @example
 * ```tsx
 * const { lists, isLoading, createList, updateList, deleteList } = useStockLists();
 *
 * // Create a new list
 * await createList({ name: 'Tech Stocks', symbols: ['AAPL', 'MSFT'] });
 *
 * // Update a list
 * await updateList(1, { name: 'Tech Giants' });
 *
 * // Delete a list
 * await deleteList(1);
 * ```
 */
export const useStockLists = (): UseStockListsResult => {
  const [lists, setLists] = useState<StockList[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch all lists from the server
   */
  const fetchLists = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await stockListService.getLists();
      setLists(response.items);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load lists';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch on mount
  useEffect(() => {
    fetchLists();
  }, [fetchLists]);

  /**
   * Create a new stock list
   * Updates local state optimistically after successful API call
   */
  const createList = useCallback(async (data: CreateStockListRequest): Promise<StockList> => {
    const newList = await stockListService.createList(data);
    // Add to local state and sort alphabetically by name
    setLists((prev) =>
      [...prev, newList].sort((a, b) => a.name.localeCompare(b.name))
    );
    return newList;
  }, []);

  /**
   * Update an existing stock list
   * Updates local state optimistically after successful API call
   */
  const updateList = useCallback(
    async (id: number, data: UpdateStockListRequest): Promise<StockList> => {
      const updated = await stockListService.updateList(id, data);
      // Update in local state and re-sort alphabetically
      setLists((prev) =>
        prev
          .map((list) => (list.id === id ? updated : list))
          .sort((a, b) => a.name.localeCompare(b.name))
      );
      return updated;
    },
    []
  );

  /**
   * Delete a stock list
   * Removes from local state after successful API call
   */
  const deleteList = useCallback(async (id: number): Promise<void> => {
    await stockListService.deleteList(id);
    // Remove from local state
    setLists((prev) => prev.filter((list) => list.id !== id));
  }, []);

  return {
    lists,
    isLoading,
    error,
    createList,
    updateList,
    deleteList,
    refetch: fetchLists,
  };
};
