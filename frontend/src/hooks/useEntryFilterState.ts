import { useCallback, useMemo, useState } from 'react';

export interface EntryFilterInitialValues {
  ibs_max_threshold?: number | null;
  ma50_filter_enabled?: boolean | null;
  circuit_breaker_atr_threshold?: number | null;
  circuit_breaker_symbol?: string | null;
}

export interface EntryFilterPresetConfig {
  ibs_max_threshold?: number;
  ma50_filter_enabled: boolean;
  circuit_breaker_atr_threshold: number;
  circuit_breaker_symbol: string;
}

export function useEntryFilterState() {
  const [ibsMaxThreshold, setIbsMaxThreshold] = useState('');
  const [ma50FilterEnabled, setMa50FilterEnabled] = useState(false);
  const [circuitBreakerThreshold, setCircuitBreakerThreshold] = useState('');
  const [circuitBreakerSymbol, setCircuitBreakerSymbol] = useState('SPY');
  // A <input type="number"> reports an unparseable entry ("2,8", "abc") as an
  // EMPTY value, which is our "filter off" sentinel. Without tracking badInput
  // separately, a typo silently disarms the filter with no error and an enabled
  // submit button — the user believes a safety gate is on when it is not.
  const [ibsBadInput, setIbsBadInput] = useState(false);
  const [cbThresholdBadInput, setCbThresholdBadInput] = useState(false);

  const validation = useMemo(() => {
    const ibsParsed = ibsMaxThreshold === '' ? null : parseFloat(ibsMaxThreshold);
    const cbThresholdParsed = circuitBreakerThreshold === '' ? null : parseFloat(circuitBreakerThreshold);

    const hasIbsError = ibsBadInput || (ibsParsed !== null && !(ibsParsed > 0 && ibsParsed <= 1));
    const hasCbThresholdError =
      cbThresholdBadInput ||
      (cbThresholdParsed !== null && !(cbThresholdParsed > 0 && isFinite(cbThresholdParsed)));
    const hasCbSymbolError =
      circuitBreakerThreshold !== '' && !/^[A-Z]{1,5}$/.test(circuitBreakerSymbol);

    return { hasIbsError, hasCbThresholdError, hasCbSymbolError };
  }, [
    ibsMaxThreshold,
    circuitBreakerThreshold,
    circuitBreakerSymbol,
    ibsBadInput,
    cbThresholdBadInput,
  ]);

  /** onChange for a number input: records the raw value and whether the browser
   * rejected it, so "" from a typo is not mistaken for "" from an empty field. */
  const handleNumberChange = useCallback(
    (
      setValue: (v: string) => void,
      setBadInput: (v: boolean) => void,
    ) => (e: React.ChangeEvent<HTMLInputElement>) => {
      setValue(e.target.value);
      setBadInput(e.target.validity?.badInput ?? false);
    },
    [],
  );

  const applyPresetFilters = useCallback((p: EntryFilterPresetConfig) => {
    setMa50FilterEnabled(p.ma50_filter_enabled);
    setCircuitBreakerThreshold(String(p.circuit_breaker_atr_threshold));
    setCircuitBreakerSymbol(p.circuit_breaker_symbol);
    setIbsMaxThreshold(p.ibs_max_threshold !== undefined ? String(p.ibs_max_threshold) : '');
    // Programmatic values are always well-formed; clear any stale typo state.
    setIbsBadInput(false);
    setCbThresholdBadInput(false);
  }, []);

  const applyInitialValues = useCallback((iv: EntryFilterInitialValues) => {
    if (iv.ibs_max_threshold != null) setIbsMaxThreshold(String(iv.ibs_max_threshold));
    if (iv.ma50_filter_enabled !== undefined && iv.ma50_filter_enabled !== null) {
      setMa50FilterEnabled(!!iv.ma50_filter_enabled);
    }
    if (iv.circuit_breaker_atr_threshold != null) {
      setCircuitBreakerThreshold(String(iv.circuit_breaker_atr_threshold));
    }
    if (iv.circuit_breaker_symbol) setCircuitBreakerSymbol(iv.circuit_breaker_symbol);
  }, []);

  return {
    ibsMaxThreshold,
    setIbsMaxThreshold,
    ma50FilterEnabled,
    setMa50FilterEnabled,
    circuitBreakerThreshold,
    setCircuitBreakerThreshold,
    circuitBreakerSymbol,
    setCircuitBreakerSymbol,
    ...validation,
    onIbsChange: handleNumberChange(setIbsMaxThreshold, setIbsBadInput),
    onCbThresholdChange: handleNumberChange(setCircuitBreakerThreshold, setCbThresholdBadInput),
    applyPresetFilters,
    applyInitialValues,
  };
}
