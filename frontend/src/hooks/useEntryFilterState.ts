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
    // The rule and its explanation live together: a form that re-derived "why"
    // from its own second predicate could show a message for a value this hook
    // considers valid the moment the accepted format changes.
    const hasCbSymbolError =
      circuitBreakerThreshold !== '' && !/^[A-Z]{1,5}$/.test(circuitBreakerSymbol);
    const cbSymbolError = !hasCbSymbolError
      ? null
      : circuitBreakerSymbol.includes('.')
        ? 'Dot-notation tickers like BRK.B are not supported'
        : 'Must be 1–5 uppercase letters (e.g. SPY)';

    // Payload-ready values: the parsed number only when it is a valid enabled
    // value, null when the filter is off OR the raw value is invalid (NaN,
    // out of range, browser-rejected). canSubmit already blocks invalid values;
    // this is defense-in-depth so a stale state can never serialize NaN -> JSON
    // null and silently disarm a filter while looking configured. The form must
    // submit these, not re-parse the raw strings.
    const ibsSubmitValue =
      !ibsBadInput && ibsParsed !== null && ibsParsed > 0 && ibsParsed <= 1 ? ibsParsed : null;
    const cbThresholdSubmitValue =
      !cbThresholdBadInput &&
      cbThresholdParsed !== null &&
      cbThresholdParsed > 0 &&
      isFinite(cbThresholdParsed)
        ? cbThresholdParsed
        : null;

    return {
      hasIbsError,
      hasCbThresholdError,
      hasCbSymbolError,
      cbSymbolError,
      ibsSubmitValue,
      cbThresholdSubmitValue,
    };
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
    // Full restore, mirroring applyPresetFilters: a replayed run must reproduce
    // the original configuration exactly, so an absent/null field is an explicit
    // "filter off" that resets to the default — not "keep whatever is in the
    // form". Skip-keep-current would let a previous edit leak into the replay.
    setIbsMaxThreshold(iv.ibs_max_threshold != null ? String(iv.ibs_max_threshold) : '');
    setMa50FilterEnabled(iv.ma50_filter_enabled ?? false);
    setCircuitBreakerThreshold(
      iv.circuit_breaker_atr_threshold != null ? String(iv.circuit_breaker_atr_threshold) : '',
    );
    setCircuitBreakerSymbol(iv.circuit_breaker_symbol || 'SPY');
    // Programmatic values are always well-formed; clear any stale typo state.
    setIbsBadInput(false);
    setCbThresholdBadInput(false);
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
