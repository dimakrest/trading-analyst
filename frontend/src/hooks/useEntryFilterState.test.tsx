import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useEntryFilterState } from './useEntryFilterState';

describe('useEntryFilterState', () => {
  it('initial state has correct defaults', () => {
    const { result } = renderHook(() => useEntryFilterState());
    expect(result.current.ibsMaxThreshold).toBe('');
    expect(result.current.ma50FilterEnabled).toBe(false);
    expect(result.current.circuitBreakerThreshold).toBe('');
    expect(result.current.circuitBreakerSymbol).toBe('SPY');
  });

  it('hasIbsError is true for out-of-range value 1.5', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => result.current.setIbsMaxThreshold('1.5'));
    expect(result.current.hasIbsError).toBe(true);
  });

  it('hasIbsError is true for negative value -0.1', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => result.current.setIbsMaxThreshold('-0.1'));
    expect(result.current.hasIbsError).toBe(true);
  });

  it('hasIbsError is false for empty string', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => result.current.setIbsMaxThreshold(''));
    expect(result.current.hasIbsError).toBe(false);
  });

  it('hasIbsError is false for in-range value 0.5', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => result.current.setIbsMaxThreshold('0.5'));
    expect(result.current.hasIbsError).toBe(false);
  });

  it('hasCbThresholdError is true for negative threshold -1', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => result.current.setCircuitBreakerThreshold('-1'));
    expect(result.current.hasCbThresholdError).toBe(true);
  });

  it('hasCbSymbolError is true for BRK.B dot-notation when threshold is set', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.setCircuitBreakerThreshold('2.8');
      result.current.setCircuitBreakerSymbol('BRK.B');
    });
    expect(result.current.hasCbSymbolError).toBe(true);
  });

  it('hasCbSymbolError is true for lowercase symbol when threshold is set', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.setCircuitBreakerThreshold('2.8');
      result.current.setCircuitBreakerSymbol('spy');
    });
    expect(result.current.hasCbSymbolError).toBe(true);
  });

  it('hasCbSymbolError is false for any symbol when threshold is empty', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.setCircuitBreakerThreshold('');
      result.current.setCircuitBreakerSymbol('BRK.B');
    });
    expect(result.current.hasCbSymbolError).toBe(false);
  });

  it('applyPresetFilters aggressive sets all fields with ibs_max_threshold undefined → empty string', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.applyPresetFilters({
        ma50_filter_enabled: true,
        circuit_breaker_atr_threshold: 2.8,
        circuit_breaker_symbol: 'SPY',
      });
    });
    expect(result.current.ibsMaxThreshold).toBe('');
    expect(result.current.ma50FilterEnabled).toBe(true);
    expect(result.current.circuitBreakerThreshold).toBe('2.8');
    expect(result.current.circuitBreakerSymbol).toBe('SPY');
  });

  it('applyPresetFilters conservative sets IBS to preset value', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.applyPresetFilters({
        ibs_max_threshold: 0.55,
        ma50_filter_enabled: true,
        circuit_breaker_atr_threshold: 2.8,
        circuit_breaker_symbol: 'SPY',
      });
    });
    expect(result.current.ibsMaxThreshold).toBe('0.55');
    expect(result.current.ma50FilterEnabled).toBe(true);
  });

  it('applyInitialValues with ma50_filter_enabled true sets ma50FilterEnabled true', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.applyInitialValues({ ma50_filter_enabled: true });
    });
    expect(result.current.ma50FilterEnabled).toBe(true);
  });

  it('applyInitialValues with undefined fields does not reset state', () => {
    const { result } = renderHook(() => useEntryFilterState());
    act(() => {
      result.current.setIbsMaxThreshold('0.5');
      result.current.setMa50FilterEnabled(true);
    });
    act(() => {
      result.current.applyInitialValues({});
    });
    expect(result.current.ibsMaxThreshold).toBe('0.5');
    expect(result.current.ma50FilterEnabled).toBe(true);
  });
});
