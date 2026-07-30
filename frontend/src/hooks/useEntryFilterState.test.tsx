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

  it('applyInitialValues with absent fields performs a full reset to defaults', () => {
    // A replayed run must reproduce the original configuration exactly: an
    // absent/null field means "filter off" and resets to the default, mirroring
    // applyPresetFilters. Keeping stale form state would leak a previous edit
    // into the replay.
    const { result } = renderHook(() => useEntryFilterState());

    // Arrange: dirty every field away from its default
    act(() => {
      result.current.setIbsMaxThreshold('0.5');
      result.current.setMa50FilterEnabled(true);
      result.current.setCircuitBreakerThreshold('2.8');
      result.current.setCircuitBreakerSymbol('QQQ');
    });

    // Act: restore a run that had no entry filters
    act(() => {
      result.current.applyInitialValues({});
    });

    // Assert: every field is back at its default
    expect(result.current.ibsMaxThreshold).toBe('');
    expect(result.current.ma50FilterEnabled).toBe(false);
    expect(result.current.circuitBreakerThreshold).toBe('');
    expect(result.current.circuitBreakerSymbol).toBe('SPY');
  });

  it('applyInitialValues with null fields resets like absent fields', () => {
    const { result } = renderHook(() => useEntryFilterState());

    act(() => {
      result.current.setIbsMaxThreshold('0.5');
      result.current.setMa50FilterEnabled(true);
      result.current.setCircuitBreakerThreshold('2.8');
      result.current.setCircuitBreakerSymbol('QQQ');
    });

    act(() => {
      result.current.applyInitialValues({
        ibs_max_threshold: null,
        ma50_filter_enabled: null,
        circuit_breaker_atr_threshold: null,
        circuit_breaker_symbol: null,
      });
    });

    expect(result.current.ibsMaxThreshold).toBe('');
    expect(result.current.ma50FilterEnabled).toBe(false);
    expect(result.current.circuitBreakerThreshold).toBe('');
    expect(result.current.circuitBreakerSymbol).toBe('SPY');
  });

  it('applyInitialValues restores all provided fields', () => {
    const { result } = renderHook(() => useEntryFilterState());

    act(() => {
      result.current.applyInitialValues({
        ibs_max_threshold: 0.55,
        ma50_filter_enabled: true,
        circuit_breaker_atr_threshold: 2.8,
        circuit_breaker_symbol: 'QQQ',
      });
    });

    expect(result.current.ibsMaxThreshold).toBe('0.55');
    expect(result.current.ma50FilterEnabled).toBe(true);
    expect(result.current.circuitBreakerThreshold).toBe('2.8');
    expect(result.current.circuitBreakerSymbol).toBe('QQQ');
  });

  it('applyInitialValues clears stale badInput flags like applyPresetFilters does', () => {
    const { result } = renderHook(() => useEntryFilterState());

    // Arrange: simulate a browser-rejected typo — value reported as '' with
    // validity.badInput true — for both number fields
    const badInputEvent = {
      target: { value: '', validity: { badInput: true } },
    } as unknown as React.ChangeEvent<HTMLInputElement>;
    act(() => {
      result.current.onIbsChange(badInputEvent);
      result.current.onCbThresholdChange(badInputEvent);
    });
    expect(result.current.hasIbsError).toBe(true);
    expect(result.current.hasCbThresholdError).toBe(true);

    // Act: programmatic restore always carries well-formed values
    act(() => {
      result.current.applyInitialValues({});
    });

    // Assert: typo state is gone
    expect(result.current.hasIbsError).toBe(false);
    expect(result.current.hasCbThresholdError).toBe(false);
  });

  describe('payload-ready submit values', () => {
    it('ibsSubmitValue is null when the field is empty (filter off)', () => {
      const { result } = renderHook(() => useEntryFilterState());
      expect(result.current.ibsSubmitValue).toBeNull();
    });

    it('ibsSubmitValue is the parsed number for a valid in-range value', () => {
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setIbsMaxThreshold('0.55'));
      expect(result.current.ibsSubmitValue).toBe(0.55);
    });

    it('ibsSubmitValue is null for an out-of-range value', () => {
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setIbsMaxThreshold('1.5'));
      expect(result.current.ibsSubmitValue).toBeNull();
    });

    it('cbThresholdSubmitValue is null when the field is empty (breaker off)', () => {
      const { result } = renderHook(() => useEntryFilterState());
      expect(result.current.cbThresholdSubmitValue).toBeNull();
    });

    it('cbThresholdSubmitValue is the parsed number for a valid value', () => {
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setCircuitBreakerThreshold('2.8'));
      expect(result.current.cbThresholdSubmitValue).toBe(2.8);
    });

    it('cbThresholdSubmitValue is null for a non-positive value', () => {
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setCircuitBreakerThreshold('-1'));
      expect(result.current.cbThresholdSubmitValue).toBeNull();
    });

    it('cbThresholdSubmitValue is null for an unparseable value instead of NaN', () => {
      // NaN would serialize to JSON null and silently disable the breaker while
      // circuit_breaker_symbol is still sent — the exact hazard the submit
      // values exist to prevent.
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setCircuitBreakerThreshold('abc'));
      expect(result.current.cbThresholdSubmitValue).toBeNull();
      expect(Number.isNaN(result.current.cbThresholdSubmitValue)).toBe(false);
    });

    it('cbThresholdSubmitValue is null for a non-finite value', () => {
      const { result } = renderHook(() => useEntryFilterState());
      act(() => result.current.setCircuitBreakerThreshold('5e999'));
      expect(result.current.cbThresholdSubmitValue).toBeNull();
    });
  });
});
