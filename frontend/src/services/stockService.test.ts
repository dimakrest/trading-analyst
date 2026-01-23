import { describe, it, expect, vi, beforeEach } from 'vitest';

// Create mock API client instance
const mockApiClient = {
  get: vi.fn(),
  post: vi.fn(),
};

// Mock apiClient before importing stockService
vi.mock('../lib/apiClient', () => ({
  apiClient: mockApiClient,
}));

describe('stockService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchStockData', () => {
    it('should fetch stock data successfully', async () => {
      // Arrange - Mock backend response format
      const mockBackendResponse = {
        symbol: 'AAPL',
        data: [
          {
            date: '2024-01-01',
            open: 140.0,
            high: 145.0,
            low: 138.0,
            close: 140.0,
            volume: 1000000,
            ma_20: null,
          },
          {
            date: '2024-01-02',
            open: 142.0,
            high: 152.0,
            low: 141.0,
            close: 150.0,
            volume: 1100000,
            ma_20: null,
          },
        ],
        total_records: 2,
        start_date: '2024-01-01',
        end_date: '2024-01-02',
      };

      mockApiClient.get.mockResolvedValue({ data: mockBackendResponse });

      // Import after mock is set up
      const { fetchStockData } = await import('./stockService');

      // Act
      const result = await fetchStockData('AAPL');

      // Assert
      expect(result.symbol).toBe('AAPL');
      expect(result.company_name).toBe('AAPL');
      expect(result.current_price).toBe(150.0);
      expect(result.price_change).toBe(10.0);
      expect(result.price_change_percent).toBeCloseTo(7.14, 1);
      expect(result.prices).toEqual(mockBackendResponse.data);
      expect(mockApiClient.get).toHaveBeenCalledWith('/v1/stocks/AAPL/prices/', {
        params: { period: '1y', interval: '1d' },
      });
    });

    it('should throw error when API call fails', async () => {
      // Arrange
      const errorMessage = 'Network Error';
      mockApiClient.get.mockRejectedValue(new Error(errorMessage));

      const { fetchStockData } = await import('./stockService');

      // Act & Assert
      await expect(fetchStockData('INVALID')).rejects.toThrow(errorMessage);
    });

    it('should call API with correct parameters', async () => {
      // Arrange
      mockApiClient.get.mockResolvedValue({
        data: {
          symbol: 'TSLA',
          data: [
            { date: '2024-01-01', open: 100, high: 105, low: 98, close: 103, volume: 500000, ma_20: null },
          ],
          total_records: 1,
          start_date: '2024-01-01',
          end_date: '2024-01-01',
        },
      });

      const { fetchStockData } = await import('./stockService');

      // Act
      await fetchStockData('TSLA');

      // Assert
      expect(mockApiClient.get).toHaveBeenCalledWith('/v1/stocks/TSLA/prices/', {
        params: { period: '1y', interval: '1d' },
      });
    });
  });

  describe('fetchStockDataByDateRange', () => {
    it('should fetch stock data for date range successfully', async () => {
      // Arrange
      const mockBackendResponse = {
        symbol: 'AAPL',
        data: [
          { date: '2024-01-01', open: 140.0, high: 145.0, low: 138.0, close: 140.0, volume: 1000000, ma_20: null },
          { date: '2024-01-31', open: 142.0, high: 152.0, low: 141.0, close: 150.0, volume: 1100000, ma_20: null },
        ],
        total_records: 2,
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      };

      mockApiClient.get.mockResolvedValue({ data: mockBackendResponse });

      const { fetchStockDataByDateRange } = await import('./stockService');

      // Act
      const result = await fetchStockDataByDateRange({
        symbol: 'AAPL',
        startDate: '2024-01-01',
        endDate: '2024-01-31',
      });

      // Assert API call
      expect(mockApiClient.get).toHaveBeenCalledWith('/v1/stocks/AAPL/prices/', {
        params: {
          start_date: '2024-01-01',
          end_date: '2024-01-31',
          interval: '1d',
        },
      });

      // Assert transformation
      expect(result.symbol).toBe('AAPL');
      expect(result.current_price).toBe(150.0);
      expect(result.price_change).toBe(10.0);
      expect(result.price_change_percent).toBeCloseTo(7.14, 1);
      expect(result.prices).toEqual(mockBackendResponse.data);
    });

    it('should throw error when no data returned', async () => {
      // Arrange
      mockApiClient.get.mockResolvedValue({
        data: { symbol: 'AAPL', data: [] }
      });

      const { fetchStockDataByDateRange } = await import('./stockService');

      // Act & Assert
      await expect(
        fetchStockDataByDateRange({
          symbol: 'AAPL',
          startDate: '2024-01-01',
          endDate: '2024-01-31',
        })
      ).rejects.toThrow('No price data available for the specified date range');
    });

    it('should handle API errors gracefully', async () => {
      // Arrange
      const error = new Error('Network error');
      mockApiClient.get.mockRejectedValue(error);

      const { fetchStockDataByDateRange } = await import('./stockService');

      // Act & Assert
      await expect(
        fetchStockDataByDateRange({
          symbol: 'AAPL',
          startDate: '2024-01-01',
          endDate: '2024-01-31',
        })
      ).rejects.toThrow('Network error');
    });
  });
});
