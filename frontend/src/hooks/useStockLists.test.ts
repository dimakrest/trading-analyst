import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useStockLists } from './useStockLists';
import { stockListService } from '../services/stockListService';

// Mock the stockListService
vi.mock('../services/stockListService', () => ({
  stockListService: {
    getLists: vi.fn(),
    getList: vi.fn(),
    createList: vi.fn(),
    updateList: vi.fn(),
    deleteList: vi.fn(),
  },
}));

describe('useStockLists', () => {
  const mockLists = [
    { id: 1, name: 'Tech', symbols: ['AAPL', 'MSFT'], symbol_count: 2 },
    { id: 2, name: 'Finance', symbols: ['JPM'], symbol_count: 1 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Load', () => {
    it('fetches lists on mount', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockResolvedValue({
        items: mockLists,
        total: 2,
        has_more: false,
      });

      // Act
      const { result } = renderHook(() => useStockLists());

      // Assert - initial loading state
      expect(result.current.isLoading).toBe(true);

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.lists).toEqual(mockLists);
      expect(result.current.error).toBeNull();
    });

    it('sets error on fetch failure', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockRejectedValue(new Error('Network error'));

      // Act
      const { result } = renderHook(() => useStockLists());

      // Wait for fetch to fail
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Assert
      expect(result.current.error).toBe('Network error');
      expect(result.current.lists).toEqual([]);
    });
  });

  describe('createList', () => {
    it('creates a new list and updates local state', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockResolvedValue({
        items: [],
        total: 0,
        has_more: false,
      });

      const newList = { id: 3, name: 'Growth', symbols: ['NVDA'], symbol_count: 1 };
      vi.mocked(stockListService.createList).mockResolvedValue(newList);

      const { result } = renderHook(() => useStockLists());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Act
      await act(async () => {
        await result.current.createList({ name: 'Growth', symbols: ['NVDA'] });
      });

      // Assert
      expect(result.current.lists).toContainEqual(newList);
    });

    it('sorts lists alphabetically after creation', async () => {
      // Arrange
      const existingLists = [
        { id: 1, name: 'Zebra', symbols: [], symbol_count: 0 },
      ];
      vi.mocked(stockListService.getLists).mockResolvedValue({
        items: existingLists,
        total: 1,
        has_more: false,
      });

      const newList = { id: 2, name: 'Alpha', symbols: [], symbol_count: 0 };
      vi.mocked(stockListService.createList).mockResolvedValue(newList);

      const { result } = renderHook(() => useStockLists());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Act
      await act(async () => {
        await result.current.createList({ name: 'Alpha' });
      });

      // Assert - Alpha should come before Zebra
      expect(result.current.lists[0].name).toBe('Alpha');
      expect(result.current.lists[1].name).toBe('Zebra');
    });
  });

  describe('updateList', () => {
    it('updates a list and reflects changes in local state', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockResolvedValue({
        items: mockLists,
        total: 2,
        has_more: false,
      });

      const updatedList = { id: 1, name: 'Updated Tech', symbols: ['AAPL', 'GOOGL'], symbol_count: 2 };
      vi.mocked(stockListService.updateList).mockResolvedValue(updatedList);

      const { result } = renderHook(() => useStockLists());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Act
      await act(async () => {
        await result.current.updateList(1, { name: 'Updated Tech', symbols: ['AAPL', 'GOOGL'] });
      });

      // Assert
      const updated = result.current.lists.find((l) => l.id === 1);
      expect(updated?.name).toBe('Updated Tech');
      expect(updated?.symbols).toEqual(['AAPL', 'GOOGL']);
    });
  });

  describe('deleteList', () => {
    it('removes a list from local state', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockResolvedValue({
        items: mockLists,
        total: 2,
        has_more: false,
      });
      vi.mocked(stockListService.deleteList).mockResolvedValue(undefined);

      const { result } = renderHook(() => useStockLists());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.lists).toHaveLength(2);

      // Act
      await act(async () => {
        await result.current.deleteList(1);
      });

      // Assert
      expect(result.current.lists).toHaveLength(1);
      expect(result.current.lists.find((l) => l.id === 1)).toBeUndefined();
    });
  });

  describe('refetch', () => {
    it('refetches lists from the server', async () => {
      // Arrange
      vi.mocked(stockListService.getLists).mockResolvedValueOnce({
        items: mockLists,
        total: 2,
        has_more: false,
      });

      const { result } = renderHook(() => useStockLists());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Set up for refetch
      const updatedLists = [
        ...mockLists,
        { id: 3, name: 'New List', symbols: [], symbol_count: 0 },
      ];
      vi.mocked(stockListService.getLists).mockResolvedValueOnce({
        items: updatedLists,
        total: 3,
        has_more: false,
      });

      // Act
      await act(async () => {
        await result.current.refetch();
      });

      // Assert
      expect(result.current.lists).toHaveLength(3);
    });
  });
});
