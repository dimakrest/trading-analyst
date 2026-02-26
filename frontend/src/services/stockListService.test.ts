import { describe, it, expect, vi, beforeEach } from 'vitest';
import { stockListService } from './stockListService';
import { apiClient } from '../lib/apiClient';

// Mock the apiClient
vi.mock('../lib/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('stockListService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getLists', () => {
    it('fetches all stock lists', async () => {
      // Arrange
      const mockResponse = {
        data: {
          items: [
            { id: 1, name: 'Tech', symbols: ['AAPL', 'MSFT'], symbol_count: 2 },
            { id: 2, name: 'Finance', symbols: ['JPM'], symbol_count: 1 },
          ],
          total: 2,
          has_more: false,
        },
      };
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.getLists();

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith('/v1/stock-lists');
      expect(result).toEqual(mockResponse.data);
      expect(result.items).toHaveLength(2);
    });

    it('throws error on API failure', async () => {
      // Arrange
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'));

      // Act & Assert
      await expect(stockListService.getLists()).rejects.toThrow('Network error');
    });
  });

  describe('getList', () => {
    it('fetches a single stock list by ID', async () => {
      // Arrange
      const mockResponse = {
        data: { id: 1, name: 'Tech', symbols: ['AAPL', 'MSFT'], symbol_count: 2 },
      };
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.getList(1);

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith('/v1/stock-lists/1');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('createList', () => {
    it('creates a new list with name only', async () => {
      // Arrange
      const mockResponse = {
        data: { id: 1, name: 'New List', symbols: [], symbol_count: 0 },
      };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.createList({ name: 'New List' });

      // Assert
      expect(apiClient.post).toHaveBeenCalledWith('/v1/stock-lists', { name: 'New List' });
      expect(result).toEqual(mockResponse.data);
    });

    it('creates a new list with symbols', async () => {
      // Arrange
      const mockResponse = {
        data: { id: 1, name: 'Tech', symbols: ['AAPL', 'MSFT'], symbol_count: 2 },
      };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.createList({
        name: 'Tech',
        symbols: ['AAPL', 'MSFT'],
      });

      // Assert
      expect(apiClient.post).toHaveBeenCalledWith('/v1/stock-lists', {
        name: 'Tech',
        symbols: ['AAPL', 'MSFT'],
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('updateList', () => {
    it('updates a list name', async () => {
      // Arrange
      const mockResponse = {
        data: { id: 1, name: 'Updated Tech', symbols: ['AAPL'], symbol_count: 1 },
      };
      vi.mocked(apiClient.put).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.updateList(1, { name: 'Updated Tech' });

      // Assert
      expect(apiClient.put).toHaveBeenCalledWith('/v1/stock-lists/1', { name: 'Updated Tech' });
      expect(result).toEqual(mockResponse.data);
    });

    it('updates list symbols', async () => {
      // Arrange
      const mockResponse = {
        data: { id: 1, name: 'Tech', symbols: ['AAPL', 'GOOGL'], symbol_count: 2 },
      };
      vi.mocked(apiClient.put).mockResolvedValue(mockResponse);

      // Act
      const result = await stockListService.updateList(1, { symbols: ['AAPL', 'GOOGL'] });

      // Assert
      expect(apiClient.put).toHaveBeenCalledWith('/v1/stock-lists/1', {
        symbols: ['AAPL', 'GOOGL'],
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('deleteList', () => {
    it('deletes a stock list', async () => {
      // Arrange
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });

      // Act
      await stockListService.deleteList(1);

      // Assert
      expect(apiClient.delete).toHaveBeenCalledWith('/v1/stock-lists/1');
    });
  });
});
