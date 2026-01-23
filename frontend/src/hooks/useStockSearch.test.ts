import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStockSearch } from './useStockSearch';

describe('useStockSearch', () => {
  it('should initialize with default symbol AAPL', () => {
    // Act
    const { result } = renderHook(() => useStockSearch());

    // Assert
    expect(result.current.symbol).toBe('AAPL');
  });

  it('should update symbol when setSymbol is called', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());

    // Act
    act(() => {
      result.current.setSymbol('TSLA');
    });

    // Assert
    expect(result.current.symbol).toBe('TSLA');
  });

  it('should handle search with uppercase conversion', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());

    // Act
    act(() => {
      result.current.handleSearch('tsla');
    });

    // Assert
    expect(result.current.symbol).toBe('TSLA');
  });

  it('should trim whitespace from search input', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());

    // Act
    act(() => {
      result.current.handleSearch('  msft  ');
    });

    // Assert
    expect(result.current.symbol).toBe('MSFT');
  });

  it('should not update symbol when search input is empty', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());
    const initialSymbol = result.current.symbol;

    // Act
    act(() => {
      result.current.handleSearch('');
    });

    // Assert
    expect(result.current.symbol).toBe(initialSymbol);
  });

  it('should not update symbol when search input is only whitespace', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());
    const initialSymbol = result.current.symbol;

    // Act
    act(() => {
      result.current.handleSearch('   ');
    });

    // Assert
    expect(result.current.symbol).toBe(initialSymbol);
  });

  it('should handle multiple searches', () => {
    // Arrange
    const { result } = renderHook(() => useStockSearch());

    // Act
    act(() => {
      result.current.handleSearch('TSLA');
    });
    expect(result.current.symbol).toBe('TSLA');

    act(() => {
      result.current.handleSearch('MSFT');
    });
    expect(result.current.symbol).toBe('MSFT');

    act(() => {
      result.current.handleSearch('googl');
    });

    // Assert
    expect(result.current.symbol).toBe('GOOGL');
  });
});
