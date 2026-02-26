import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useStockData } from './useStockData';
import * as stockService from '../services/stockService';
import type { StockData, IndicatorsResponse } from '../types/stock';

vi.mock('../services/stockService');

describe('useStockData', () => {
  const mockStockData: StockData = {
    symbol: 'AAPL',
    company_name: 'Apple Inc.',
    current_price: 150.0,
    price_change: 15.23,
    price_change_percent: 10.25,
    prices: [],
  };

  const mockIndicatorsResponse: IndicatorsResponse = {
    symbol: 'AAPL',
    data: [],
    total_records: 0,
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    interval: '1d',
    indicators: ['ma_20', 'cci'],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch stock data on mount', async () => {
    // Arrange
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue(mockStockData);
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result } = renderHook(() => useStockData('AAPL'));

    // Assert - initial state
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBe(null);
    expect(result.current.error).toBe(null);

    // Wait for data to load
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockStockData);
    expect(result.current.error).toBe(null);
    expect(stockService.fetchStockData).toHaveBeenCalledWith('AAPL', '1d');
    expect(stockService.fetchIndicators).toHaveBeenCalledWith('AAPL', '1d');
  });

  it('should handle fetch errors', async () => {
    // Arrange
    const errorMessage = 'Network error';
    vi.spyOn(stockService, 'fetchStockData').mockRejectedValue(new Error(errorMessage));
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result } = renderHook(() => useStockData('AAPL'));

    // Wait for error state
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Assert
    expect(result.current.error).toBe(errorMessage);
    expect(result.current.data).toBe(null);
  });

  it('should refetch data when refetch is called', async () => {
    // Arrange
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue(mockStockData);
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result } = renderHook(() => useStockData('AAPL'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Clear mock and refetch
    vi.clearAllMocks();
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue({
      ...mockStockData,
      current_price: 160.0,
    });
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    await act(async () => {
      await result.current.refetch();
    });

    // Assert
    await waitFor(() => {
      expect(result.current.data?.current_price).toBe(160.0);
    });
    expect(stockService.fetchStockData).toHaveBeenCalledTimes(1);
    expect(stockService.fetchIndicators).toHaveBeenCalledTimes(1);
  });

  it('should not fetch when symbol is empty', async () => {
    // Arrange
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue(mockStockData);
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result } = renderHook(() => useStockData(''));

    // Wait a bit
    await new Promise((resolve) => setTimeout(resolve, 100));

    // Assert
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBe(null);
    expect(stockService.fetchStockData).not.toHaveBeenCalled();
    expect(stockService.fetchIndicators).not.toHaveBeenCalled();
  });

  it('should refetch when symbol changes', async () => {
    // Arrange
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue(mockStockData);
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result, rerender } = renderHook(
      ({ symbol }) => useStockData(symbol),
      {
        initialProps: { symbol: 'AAPL' },
      }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(stockService.fetchStockData).toHaveBeenCalledWith('AAPL', '1d');
    expect(stockService.fetchIndicators).toHaveBeenCalledWith('AAPL', '1d');

    // Change symbol
    vi.clearAllMocks();
    vi.spyOn(stockService, 'fetchStockData').mockResolvedValue({
      ...mockStockData,
      symbol: 'TSLA',
    });
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue({
      ...mockIndicatorsResponse,
      symbol: 'TSLA',
    });

    rerender({ symbol: 'TSLA' });

    await waitFor(() => {
      expect(stockService.fetchStockData).toHaveBeenCalledWith('TSLA', '1d');
      expect(stockService.fetchIndicators).toHaveBeenCalledWith('TSLA', '1d');
    });
  });

  it('should handle non-Error exceptions', async () => {
    // Arrange
    vi.spyOn(stockService, 'fetchStockData').mockRejectedValue('String error');
    vi.spyOn(stockService, 'fetchIndicators').mockResolvedValue(mockIndicatorsResponse);

    // Act
    const { result } = renderHook(() => useStockData('AAPL'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Assert
    expect(result.current.error).toBe('Failed to fetch stock data');
  });
});
