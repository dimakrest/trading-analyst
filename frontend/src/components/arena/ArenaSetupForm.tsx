/**
 * Arena Setup Form
 *
 * Form for configuring and starting a new trading simulation.
 * Split into three tabs: Setup, Agent, and Portfolio.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Check, ChevronRight, Play } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Slider } from '../ui/slider';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { ListSelector } from '../molecules/ListSelector';
import { useStockLists } from '../../hooks/useStockLists';
import { useAgentConfigs } from '../../hooks/useAgentConfigs';
import { useEntryFilterState } from '../../hooks/useEntryFilterState';
import { PORTFOLIO_STRATEGIES } from '../../constants/portfolio';
import { cn } from '../../lib/utils';
import type { CreateComparisonRequest, CreateSimulationRequest } from '../../types/arena';

// Arena configuration constants
const MAX_ARENA_SYMBOLS = 600;

interface ArenaSetupFormProps {
  /** Callback when form is submitted with a single strategy */
  onSubmit: (request: CreateSimulationRequest) => Promise<void>;
  /** Callback when form is submitted with 2+ strategies (comparison mode) */
  onSubmitComparison: (request: CreateComparisonRequest) => Promise<void>;
  /** Whether submission is in progress */
  isLoading: boolean;
  /** Initial values for form pre-population (e.g., from replay) */
  initialValues?: {
    symbols: string[];
    start_date: string;
    end_date: string;
    initial_capital: number;
    position_size: number;
    trailing_stop_pct: number;
    min_buy_score: number;
    stock_list_id?: number | null;
    stock_list_name?: string | null;
    agent_config_id?: number | null;
    portfolio_strategy?: string;
    max_per_sector?: number | null;
    max_open_positions?: number | null;
    sizing_mode?: 'fixed' | 'fixed_pct' | 'risk_based' | null;
    stop_type?: 'fixed' | 'atr';
    atr_stop_multiplier?: number | null;
    atr_stop_min_pct?: number | null;
    atr_stop_max_pct?: number | null;
    risk_per_trade_pct?: number | null;
    win_streak_bonus_pct?: number | null;
    max_risk_pct?: number | null;
    ibs_max_threshold?: number | null;
    ma50_filter_enabled?: boolean;
    circuit_breaker_atr_threshold?: number | null;
    circuit_breaker_symbol?: string;
  };
}

/** Minimum buy score configuration constants
 *
 * CRITICAL: STEP=5 supports graduated scoring (RSI-2)
 * MIN=5 provides safety guard against meaningless "buy everything" simulations
 */
const MIN_BUY_SCORE_CONFIG = {
  MIN: 5,
  MAX: 100,
  STEP: 5,
  DEFAULT: 60,
} as const;

/**
 * Parse symbols from text input
 *
 * Splits by comma, space, or newline, uppercases, and filters valid symbols.
 * Valid symbols are 1-10 characters alphanumeric.
 */
const parseSymbols = (text: string): string[] => {
  return text
    .split(/[,\s\n]+/)
    .map((s) => s.trim().toUpperCase())
    .filter((s) => s.length > 0 && s.length <= 10 && /^[A-Z0-9.]+$/.test(s));
};

/**
 * Validate minimum buy score is within acceptable range
 */
const isValidMinBuyScore = (score: number): boolean => {
  return score >= MIN_BUY_SCORE_CONFIG.MIN && score <= MIN_BUY_SCORE_CONFIG.MAX;
};

/**
 * Get dynamic help text based on minimum buy score.
 *
 * Trend is an eligibility filter (non-scoring). Buy threshold applies to the
 * weighted total from MA20 distance, candle pattern, volume, and momentum.
 */
const getMinBuyScoreHelpText = (score: number): string => {
  if (score >= 80) {
    return 'Trend must be bearish. This threshold is very selective and requires strong weighted confirmation.';
  }
  if (score >= 60) {
    return 'Trend must be bearish. This threshold balances selectivity and trade frequency.';
  }
  if (score >= 40) {
    return 'Trend must be bearish. This threshold allows moderate setups based on weighted signals.';
  }
  return 'Trend must be bearish. This threshold is permissive and may increase trade frequency.';
};

/** Strategy presets for one-click setup. Populate stop, sizing, constraints, and filter fields.
 * Do NOT modify selectedStrategies, symbols, dates, or capital. */
const STRATEGY_PRESETS = {
  aggressive: {
    stop_type: 'atr' as const,
    atr_stop_multiplier: 2.0,
    sizing_mode: 'risk_based' as const,
    risk_per_trade_pct: 2.5,
    max_open_positions: 10,
    max_per_sector: 3,
    ibs_max_threshold: undefined as number | undefined,
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    circuit_breaker_symbol: 'SPY',
  },
  conservative: {
    stop_type: 'atr' as const,
    atr_stop_multiplier: 2.5,
    sizing_mode: 'risk_based' as const,
    risk_per_trade_pct: 2.5,
    max_open_positions: 10,
    max_per_sector: 3,
    ibs_max_threshold: 0.55,
    ma50_filter_enabled: true,
    circuit_breaker_atr_threshold: 2.8,
    circuit_breaker_symbol: 'SPY',
  },
} as const;

/** Map volatility value to a Tailwind bg color class for the indicator dot */
const volatilityDotClass: Record<string, string> = {
  calm: 'bg-green-500',
  balanced: 'bg-amber-500',
  volatile: 'bg-red-500',
  neutral: 'bg-muted-foreground',
};

/** Human-readable category labels for the strategy card tag */
const categoryLabel: Record<string, string> = {
  basic: 'Basic',
  'score-ranked': 'Score-Ranked',
  'multi-factor': 'Multi-Factor',
};

/**
 * Arena Setup Form Component
 *
 * Features:
 * - Tab-based layout: Setup / Agent / Portfolio
 * - Multi-line textarea for symbols (comma, space, or newline separated)
 * - Date range picker (start and end dates)
 * - Capital settings (initial capital and position size)
 * - Trailing stop percentage
 * - Strategy cards with volatility indicators
 * - Collapsible advanced tuning (multi-factor only)
 * - Submit button always visible below tabs
 */
export const ArenaSetupForm = ({
  onSubmit,
  onSubmitComparison,
  isLoading,
  initialValues,
}: ArenaSetupFormProps) => {
  const [symbols, setSymbols] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [capital, setCapital] = useState('10000');
  const [positionSize, setPositionSize] = useState('1000');
  const [trailingStopPct, setTrailingStopPct] = useState('5');
  const [minBuyScore, setMinBuyScore] = useState(MIN_BUY_SCORE_CONFIG.DEFAULT.toString());
  const [selectedListId, setSelectedListId] = useState<number | null>(null);
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(['none']);
  const [maxPerSector, setMaxPerSector] = useState('2');
  const [maxOpenPositions, setMaxOpenPositions] = useState('');
  const [maSweetSpotCenter, setMaSweetSpotCenter] = useState('8.5');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [entryFiltersOpen, setEntryFiltersOpen] = useState(false);
  // Stop type and ATR parameters
  const [stopType, setStopType] = useState<'fixed' | 'atr'>('fixed');
  const [atrStopMultiplier, setAtrStopMultiplier] = useState('2.0');
  const [atrStopMinPct, setAtrStopMinPct] = useState('2.0');
  const [atrStopMaxPct, setAtrStopMaxPct] = useState('10.0');
  // Sizing mode and risk parameters
  const [sizingMode, setSizingMode] = useState<'fixed' | 'fixed_pct' | 'risk_based'>('fixed');
  const [positionSizePct, setPositionSizePct] = useState('33');
  const [riskPerTradePct, setRiskPerTradePct] = useState('2.5');
  const [winStreakBonusPct, setWinStreakBonusPct] = useState('0.3');
  const [maxRiskPct, setMaxRiskPct] = useState('4.0');
  // Entry filters
  const entryFilters = useEntryFilterState();
  const {
    ibsMaxThreshold, setIbsMaxThreshold,
    ma50FilterEnabled, setMa50FilterEnabled,
    circuitBreakerThreshold, setCircuitBreakerThreshold,
    circuitBreakerSymbol, setCircuitBreakerSymbol,
  } = entryFilters;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  /** Tracks whether ATR stop was auto-set by switching to risk_based sizing */
  const atrAutoSetByRiskSizing = useRef(false);

  // Fetch stock lists
  const { lists, isLoading: listsLoading, error: listsError } = useStockLists();
  const selectedList = lists.find((l) => l.id === selectedListId) ?? null;

  // Fetch agent configs
  const {
    configs: agentConfigs,
    selectedConfigId: selectedAgentConfigId,
    setSelectedConfigId: setSelectedAgentConfigId,
    isLoading: agentConfigsLoading,
    error: agentConfigsError,
  } = useAgentConfigs();

  // Show toast if configs fail to load
  useEffect(() => {
    if (agentConfigsError) {
      toast.error(agentConfigsError);
    }
  }, [agentConfigsError]);

  // Populate form when initialValues are provided (e.g., from replay)
  useEffect(() => {
    if (initialValues) {
      setSymbols(initialValues.symbols.join(', '));
      setStartDate(initialValues.start_date);
      setEndDate(initialValues.end_date);
      setCapital(initialValues.initial_capital.toString());
      setPositionSize(initialValues.position_size.toString());
      setTrailingStopPct(initialValues.trailing_stop_pct.toString());
      setMinBuyScore(initialValues.min_buy_score.toString());
      // Always set list ID (including null for custom symbols)
      setSelectedListId(initialValues.stock_list_id ?? null);
      // Set agent config ID from replay if available
      if (initialValues.agent_config_id) {
        setSelectedAgentConfigId(initialValues.agent_config_id);
      }
      // Set portfolio strategy fields if available
      if (initialValues.portfolio_strategy != null) {
        setSelectedStrategies([initialValues.portfolio_strategy]);
      }
      if (initialValues.max_per_sector != null) {
        setMaxPerSector(initialValues.max_per_sector.toString());
      }
      if (initialValues.max_open_positions != null) {
        setMaxOpenPositions(initialValues.max_open_positions.toString());
      }
      // Set sizing mode from replay (default to 'fixed' for old simulations without this field)
      setSizingMode(initialValues.sizing_mode ?? 'fixed');
      // Set stop type and ATR params from replay
      if (initialValues.stop_type) {
        setStopType(initialValues.stop_type);
      }
      if (initialValues.atr_stop_multiplier != null) {
        setAtrStopMultiplier(initialValues.atr_stop_multiplier.toString());
      }
      if (initialValues.atr_stop_min_pct != null) {
        setAtrStopMinPct(initialValues.atr_stop_min_pct.toString());
      }
      if (initialValues.atr_stop_max_pct != null) {
        setAtrStopMaxPct(initialValues.atr_stop_max_pct.toString());
      }
      if (initialValues.risk_per_trade_pct != null) {
        setRiskPerTradePct(initialValues.risk_per_trade_pct.toString());
      }
      if (initialValues.win_streak_bonus_pct != null) {
        setWinStreakBonusPct(initialValues.win_streak_bonus_pct.toString());
      }
      if (initialValues.max_risk_pct != null) {
        setMaxRiskPct(initialValues.max_risk_pct.toString());
      }
      entryFilters.applyInitialValues(initialValues);
      // Focus textarea after population
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }, [initialValues]);

  /**
   * Handle list selection.
   * Populates the textarea with symbols from the selected list.
   */
  const handleListSelect = (listId: number | null) => {
    setSelectedListId(listId);
    if (listId !== null) {
      const list = lists.find((l) => l.id === listId);
      if (list && list.symbols.length > 0) {
        setSymbols(list.symbols.join(', '));
        setTimeout(() => textareaRef.current?.focus(), 0);
      }
    }
  };

  /**
   * Handle sizing mode change.
   * When risk_based is selected, ATR stops are required — auto-set stop_type to 'atr'.
   *
   * The atrAutoSetByRiskSizing ref tracks whether *we* flipped stop_type
   * to 'atr' for the user. If the user had ATR selected independently
   * before switching sizing modes, we must not later revert it to 'fixed'.
   */
  const handleSizingModeChange = (value: string) => {
    setSizingMode(value as 'fixed' | 'fixed_pct' | 'risk_based');
    if (value === 'risk_based') {
      // Only flip stop_type if it isn't already ATR — preserves the
      // "user chose ATR manually" signal in the ref.
      if (stopType !== 'atr') {
        setStopType('atr');
        atrAutoSetByRiskSizing.current = true;
      }
    } else if (atrAutoSetByRiskSizing.current) {
      // Only reset to fixed if ATR was auto-set by risk_based — not if user chose ATR independently
      setStopType('fixed');
      atrAutoSetByRiskSizing.current = false;
    }
  };

  /** Apply a strategy preset. Populates stop, sizing, constraints, and filter fields.
   * Does NOT modify selectedStrategies, symbols, dates, or capital. */
  const applyPreset = (preset: keyof typeof STRATEGY_PRESETS) => {
    const p = STRATEGY_PRESETS[preset];
    setStopType(p.stop_type);
    setAtrStopMultiplier(String(p.atr_stop_multiplier));
    setSizingMode(p.sizing_mode);
    setRiskPerTradePct(String(p.risk_per_trade_pct));
    setMaxOpenPositions(String(p.max_open_positions));
    setMaxPerSector(String(p.max_per_sector));
    entryFilters.applyPresetFilters(p);
    // risk_based forces ATR; mark as auto-set
    atrAutoSetByRiskSizing.current = true;
  };

  /** Toggle a portfolio strategy on or off */
  const handleStrategyToggle = (strategyName: string) => {
    setSelectedStrategies((prev) => {
      if (prev.includes(strategyName)) {
        return prev.filter((s) => s !== strategyName);
      }
      return [...prev, strategyName];
    });
  };

  const handleSubmit = useCallback(async () => {
    const symbolList = parseSymbols(symbols);
    if (symbolList.length === 0) return;

    // Only send portfolio constraints when any non-"none" strategy is selected
    const hasStrategy = selectedStrategies.some((s) => s !== 'none');
    const parsedMaxPerSector = hasStrategy && maxPerSector ? parseInt(maxPerSector, 10) : null;
    const parsedMaxOpenPositions =
      hasStrategy && maxOpenPositions ? parseInt(maxOpenPositions, 10) : null;

    // Only send ma_sweet_spot_center when an enriched_score strategy is selected
    const hasEnrichedScore = selectedStrategies.some(
      (s) => s === 'enriched_score' || s === 'enriched_score_high_atr',
    );
    const parsedMaSweetSpotCenter =
      hasEnrichedScore && maSweetSpotCenter ? parseFloat(maSweetSpotCenter) : undefined;

    const atrStopFields =
      stopType === 'atr'
        ? {
            atr_stop_multiplier: parseFloat(atrStopMultiplier),
            atr_stop_min_pct: parseFloat(atrStopMinPct),
            atr_stop_max_pct: parseFloat(atrStopMaxPct),
          }
        : {};

    // 'fixed' is the backend default — omit sizing fields entirely to keep the payload clean.
    let sizingFields: Partial<CreateSimulationRequest> = {};
    if (sizingMode === 'fixed_pct') {
      sizingFields = { sizing_mode: 'fixed_pct', position_size_pct: parseFloat(positionSizePct) };
    } else if (sizingMode === 'risk_based') {
      sizingFields = {
        sizing_mode: 'risk_based',
        risk_per_trade_pct: parseFloat(riskPerTradePct),
        win_streak_bonus_pct: parseFloat(winStreakBonusPct),
        max_risk_pct: parseFloat(maxRiskPct),
      };
    }

    // position_size is meaningful only for the default 'fixed' mode.
    const positionSizeField =
      sizingMode === 'fixed' ? { position_size: parseFloat(positionSize) } : {};

    // IBS entry filter: empty input = omit (disabled). Defense-in-depth range
    // check here in case handleSubmit is ever reached with a stale/invalid value
    // (hasIbsError/canSubmit already gates the button path).
    const ibsSubmit = ibsMaxThreshold === '' ? null : parseFloat(ibsMaxThreshold);
    const cbThresholdSubmit =
      circuitBreakerThreshold !== '' ? parseFloat(circuitBreakerThreshold) : undefined;

    const entryFilterFields: Partial<CreateSimulationRequest> = {
      ...(ibsSubmit !== null && ibsSubmit > 0 && ibsSubmit <= 1
        ? { ibs_max_threshold: ibsSubmit }
        : {}),
      ma50_filter_enabled: ma50FilterEnabled,
      ...(cbThresholdSubmit !== undefined
        ? { circuit_breaker_atr_threshold: cbThresholdSubmit, circuit_breaker_symbol: circuitBreakerSymbol }
        : {}),
    };

    if (selectedStrategies.length >= 2) {
      await onSubmitComparison({
        symbols: symbolList,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(capital),
        ...positionSizeField,
        stop_type: stopType,
        ...atrStopFields,
        trailing_stop_pct: parseFloat(trailingStopPct),
        min_buy_score: parseFloat(minBuyScore),
        stock_list_id: selectedList?.id,
        stock_list_name: selectedList?.name,
        agent_config_id: selectedAgentConfigId,
        portfolio_strategies: selectedStrategies,
        max_per_sector: parsedMaxPerSector,
        max_open_positions: parsedMaxOpenPositions,
        ...sizingFields,
        ...entryFilterFields,
      });
    } else {
      await onSubmit({
        symbols: symbolList,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(capital),
        ...positionSizeField,
        stop_type: stopType,
        ...atrStopFields,
        trailing_stop_pct: parseFloat(trailingStopPct),
        min_buy_score: parseFloat(minBuyScore),
        stock_list_id: selectedList?.id,
        stock_list_name: selectedList?.name,
        agent_config_id: selectedAgentConfigId,
        portfolio_strategy: selectedStrategies[0] ?? 'none',
        max_per_sector: parsedMaxPerSector,
        max_open_positions: parsedMaxOpenPositions,
        ma_sweet_spot_center: parsedMaSweetSpotCenter,
        ...sizingFields,
        ...entryFilterFields,
      });
    }
  }, [
    symbols,
    startDate,
    endDate,
    capital,
    positionSize,
    stopType,
    atrStopMultiplier,
    atrStopMinPct,
    atrStopMaxPct,
    trailingStopPct,
    minBuyScore,
    selectedList,
    selectedAgentConfigId,
    selectedStrategies,
    maxPerSector,
    maxOpenPositions,
    maSweetSpotCenter,
    sizingMode,
    positionSizePct,
    riskPerTradePct,
    winStreakBonusPct,
    maxRiskPct,
    ibsMaxThreshold,
    ma50FilterEnabled,
    circuitBreakerThreshold,
    circuitBreakerSymbol,
    onSubmit,
    onSubmitComparison,
  ]);

  const symbolList = parseSymbols(symbols);
  const hasValidSymbols = symbolList.length > 0 && symbolList.length <= MAX_ARENA_SYMBOLS;
  const hasValidDates = startDate && endDate && new Date(startDate) < new Date(endDate);
  const hasValidCapital = parseFloat(capital) > 0;
  const hasValidTrailingStop =
    parseFloat(trailingStopPct) > 0 && parseFloat(trailingStopPct) <= 100;
  const hasValidMinBuyScore = isValidMinBuyScore(parseFloat(minBuyScore));

  const hasStrategySelected = selectedStrategies.length > 0;
  const hasEnrichedScoreStrategy = selectedStrategies.some(
    (s) => s === 'enriched_score' || s === 'enriched_score_high_atr',
  );
  const hasNonNoneStrategy = selectedStrategies.some((s) => s !== 'none');

  const isAtrStop = stopType === 'atr';
  const isFixedPctSizing = sizingMode === 'fixed_pct';
  const isRiskBasedSizing = sizingMode === 'risk_based';

  // Circuit breaker error message (depends on symbol value, stays in form)
  const cbSymbolHasDot = circuitBreakerSymbol.includes('.');
  const { hasIbsError, hasCbThresholdError, hasCbSymbolError } = entryFilters;
  const cbSymbolErrorMessage = cbSymbolHasDot
    ? 'Dot-notation tickers like BRK.B are not supported'
    : 'Must be 1–5 uppercase letters (e.g. SPY)';

  const hasValidPositionSize =
    isRiskBasedSizing || isFixedPctSizing || parseFloat(positionSize) > 0;

  const hasValidFixedPctFields =
    !isFixedPctSizing || parseFloat(positionSizePct) > 0;

  const hasValidRiskFields =
    !isRiskBasedSizing || (
      parseFloat(riskPerTradePct) > 0 &&
      parseFloat(winStreakBonusPct) >= 0 &&
      parseFloat(maxRiskPct) > 0
    );

  const canSubmit =
    hasValidSymbols &&
    hasValidDates &&
    hasValidCapital &&
    hasValidPositionSize &&
    hasValidFixedPctFields &&
    hasValidRiskFields &&
    hasValidTrailingStop &&
    hasValidMinBuyScore &&
    hasStrategySelected &&
    !hasIbsError &&
    !hasCbThresholdError &&
    !hasCbSymbolError &&
    !isLoading;

  let submitButtonLabel = 'Start Simulation';
  if (isLoading) {
    submitButtonLabel = 'Creating...';
  } else if (selectedStrategies.length === 0) {
    submitButtonLabel = 'Select a Strategy';
  } else if (selectedStrategies.length >= 2) {
    submitButtonLabel = `Start Comparison (${selectedStrategies.length} strategies)`;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Setup Simulation</CardTitle>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => applyPreset('aggressive')}
              disabled={isLoading}
              className="text-xs font-medium px-2.5 py-1 rounded border border-border bg-background hover:bg-accent/10 hover:border-muted-foreground/50 transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50"
              aria-label="Load Aggressive preset"
            >
              Load Aggressive
            </button>
            <button
              type="button"
              onClick={() => applyPreset('conservative')}
              disabled={isLoading}
              className="text-xs font-medium px-2.5 py-1 rounded border border-border bg-background hover:bg-accent/10 hover:border-muted-foreground/50 transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50"
              aria-label="Load Conservative preset"
            >
              Load Conservative
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs defaultValue="setup">
          <TabsList className="w-full">
            <TabsTrigger value="setup" className="flex-1">
              Setup
            </TabsTrigger>
            <TabsTrigger value="agent" className="flex-1">
              Agent
            </TabsTrigger>
            <TabsTrigger value="portfolio" className="flex-1">
              Portfolio
            </TabsTrigger>
          </TabsList>

          {/* ─── Setup Tab ─── */}
          <TabsContent value="setup" className="space-y-4 pt-2">
            {/* Stock List Selector */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 sm:max-w-xs">
                <ListSelector
                  lists={lists}
                  selectedListId={selectedListId}
                  onSelect={handleListSelect}
                  isLoading={listsLoading || isLoading}
                />
              </div>
              {selectedList && (
                <div className="flex items-center">
                  <Badge
                    variant="outline"
                    className="text-xs"
                    aria-label={`Selected list: ${selectedList.name} with ${selectedList.symbol_count} symbols`}
                  >
                    {selectedList.symbol_count} symbols from "{selectedList.name}"
                  </Badge>
                </div>
              )}
            </div>

            {/* List fetch error */}
            {listsError && (
              <p className="text-sm text-destructive">Failed to load stock lists</p>
            )}

            {/* Symbols Input */}
            <div>
              <Label htmlFor="arena-symbols">Symbols</Label>
              <Textarea
                ref={textareaRef}
                id="arena-symbols"
                placeholder="AAPL, NVDA, TSLA, AMD, MSFT"
                value={symbols}
                onChange={(e) => setSymbols(e.target.value)}
                rows={3}
                className="mt-1 font-mono text-sm"
                disabled={isLoading}
              />
              <p className="text-xs text-muted-foreground mt-1">
                {selectedList
                  ? 'Symbols populated from list. You can modify them before starting.'
                  : `${symbolList.length} symbol${symbolList.length !== 1 ? 's' : ''} (max ${MAX_ARENA_SYMBOLS})`}
              </p>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="arena-start-date">Start Date</Label>
                <Input
                  id="arena-start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="mt-1"
                  disabled={isLoading}
                />
              </div>
              <div>
                <Label htmlFor="arena-end-date">End Date</Label>
                <Input
                  id="arena-end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="mt-1"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Capital Settings — drop to 2 columns when risk-based hides the size cell */}
            <div
              className={`grid gap-4 ${isRiskBasedSizing ? 'grid-cols-2' : 'grid-cols-3'}`}
            >
              <div>
                <Label htmlFor="arena-capital">Capital ($)</Label>
                <Input
                  id="arena-capital"
                  type="number"
                  min="1"
                  value={capital}
                  onChange={(e) => setCapital(e.target.value)}
                  className="mt-1"
                  disabled={isLoading}
                />
              </div>
              {/* Position Size — hidden when risk-based or fixed_pct sizing is active */}
              {!isRiskBasedSizing && !isFixedPctSizing && (
                <div>
                  <Label htmlFor="arena-position-size">Position Size ($)</Label>
                  <Input
                    id="arena-position-size"
                    type="number"
                    min="1"
                    value={positionSize}
                    onChange={(e) => setPositionSize(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
              )}
              {/* Position Size % — shown when fixed_pct sizing is active */}
              {isFixedPctSizing && (
                <div>
                  <Label htmlFor="arena-position-size-pct">Position Size (%)</Label>
                  <Input
                    id="arena-position-size-pct"
                    type="number"
                    min="0.1"
                    max="100"
                    step="0.5"
                    value={positionSizePct}
                    onChange={(e) => setPositionSizePct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
              )}
              <div>
                <Label htmlFor="arena-trailing-stop">Trailing Stop (%)</Label>
                <Input
                  id="arena-trailing-stop"
                  type="number"
                  min="0.1"
                  max="100"
                  step="0.5"
                  value={trailingStopPct}
                  onChange={(e) => setTrailingStopPct(e.target.value)}
                  className="mt-1"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Stop Type */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="arena-stop-type">Stop Type</Label>
                <Select
                  value={stopType}
                  onValueChange={(v) => setStopType(v as 'fixed' | 'atr')}
                  disabled={isRiskBasedSizing || isLoading}
                >
                  <SelectTrigger id="arena-stop-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fixed">Fixed %</SelectItem>
                    <SelectItem value="atr">ATR-Based</SelectItem>
                  </SelectContent>
                </Select>
                {isRiskBasedSizing && (
                  <p className="text-xs text-muted-foreground">
                    Required by risk-based sizing
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="arena-sizing-mode">Sizing Mode</Label>
                <Select
                  value={sizingMode}
                  onValueChange={handleSizingModeChange}
                  disabled={isLoading}
                >
                  <SelectTrigger id="arena-sizing-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fixed">Fixed $</SelectItem>
                    <SelectItem value="fixed_pct">Fixed % of Equity</SelectItem>
                    <SelectItem value="risk_based">Risk-Based (ATR)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* ATR Stop Parameters — shown when stop_type is 'atr' */}
            {isAtrStop && (
              <div className="grid grid-cols-3 gap-4 pt-1">
                <div>
                  <Label htmlFor="arena-atr-multiplier">ATR Multiplier</Label>
                  <Input
                    id="arena-atr-multiplier"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={atrStopMultiplier}
                    onChange={(e) => setAtrStopMultiplier(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <Label htmlFor="arena-atr-min">ATR Min (%)</Label>
                  <Input
                    id="arena-atr-min"
                    type="number"
                    min="0.1"
                    step="0.5"
                    value={atrStopMinPct}
                    onChange={(e) => setAtrStopMinPct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <Label htmlFor="arena-atr-max">ATR Max (%)</Label>
                  <Input
                    id="arena-atr-max"
                    type="number"
                    min="0.1"
                    step="0.5"
                    value={atrStopMaxPct}
                    onChange={(e) => setAtrStopMaxPct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
              </div>
            )}

            {/* Risk-Based Sizing Parameters — shown when sizing_mode is 'risk_based' */}
            {isRiskBasedSizing && (
              <div className="grid grid-cols-3 gap-4 pt-1">
                <div>
                  <Label htmlFor="arena-risk-per-trade">Risk Per Trade (%)</Label>
                  <Input
                    id="arena-risk-per-trade"
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    value={riskPerTradePct}
                    onChange={(e) => setRiskPerTradePct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Base risk % of equity</p>
                </div>
                <div>
                  <Label htmlFor="arena-win-streak-bonus">Win Streak Bonus (%)</Label>
                  <Input
                    id="arena-win-streak-bonus"
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={winStreakBonusPct}
                    onChange={(e) => setWinStreakBonusPct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Extra % per win streak</p>
                </div>
                <div>
                  <Label htmlFor="arena-max-risk">Max Risk Cap (%)</Label>
                  <Input
                    id="arena-max-risk"
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    value={maxRiskPct}
                    onChange={(e) => setMaxRiskPct(e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground mt-1">Maximum risk cap</p>
                </div>
              </div>
            )}
          </TabsContent>

          {/* ─── Agent Tab ─── */}
          <TabsContent value="agent" className="space-y-4 pt-2">
            {/* Agent Type indicator */}
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Agent Configuration</h3>
              <Badge variant="secondary" className="text-xs">
                Live20 mean reversion
              </Badge>
            </div>

            {/* Agent Config Selector */}
            <div className="space-y-2">
              <Label htmlFor="arena-agent-config">Agent</Label>
              <Select
                value={selectedAgentConfigId?.toString()}
                onValueChange={(value) => setSelectedAgentConfigId(Number(value))}
                disabled={agentConfigsLoading || isLoading}
              >
                <SelectTrigger id="arena-agent-config">
                  <SelectValue placeholder="Select agent..." />
                </SelectTrigger>
                <SelectContent>
                  {agentConfigs.map((config) => (
                    <SelectItem key={config.id} value={config.id.toString()}>
                      {config.name}
                      <span className="text-xs text-muted-foreground ml-2">
                        ({config.scoring_algorithm.toUpperCase()})
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Scoring algorithm used for momentum criterion evaluation
              </p>
            </div>

            {/* Minimum Buy Score */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="arena-min-buy-score-input">Minimum Buy Score</Label>
                <span className="text-sm font-medium text-muted-foreground">{minBuyScore}</span>
              </div>

              <Slider
                min={MIN_BUY_SCORE_CONFIG.MIN}
                max={MIN_BUY_SCORE_CONFIG.MAX}
                step={MIN_BUY_SCORE_CONFIG.STEP}
                value={[parseFloat(minBuyScore)]}
                onValueChange={(value) => setMinBuyScore(value[0].toString())}
                disabled={isLoading}
                className="py-4"
                aria-label="Minimum buy score slider"
              />

              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>More Trades</span>
                <span>Fewer Trades</span>
              </div>

              <Input
                id="arena-min-buy-score-input"
                type="number"
                min={MIN_BUY_SCORE_CONFIG.MIN}
                max={MIN_BUY_SCORE_CONFIG.MAX}
                step={MIN_BUY_SCORE_CONFIG.STEP}
                value={minBuyScore}
                onChange={(e) => setMinBuyScore(e.target.value)}
                disabled={isLoading}
                className="mt-2"
              />

              <p className="text-xs text-muted-foreground mt-2">
                {getMinBuyScoreHelpText(parseFloat(minBuyScore))}
              </p>
            </div>
          </TabsContent>

          {/* ─── Portfolio Tab ─── */}
          <TabsContent value="portfolio" className="space-y-4 pt-2">
            {/* Strategy Cards */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Selection Strategy</Label>
                {selectedStrategies.length >= 2 && (
                  <Badge variant="secondary" className="text-xs">
                    Comparison mode
                  </Badge>
                )}
              </div>

              <div
                className="grid grid-cols-2 gap-2"
                role="group"
                aria-label="Portfolio strategies"
              >
                {PORTFOLIO_STRATEGIES.map((strategy) => {
                  const isSelected = selectedStrategies.includes(strategy.name);
                  return (
                    <button
                      key={strategy.name}
                      type="button"
                      onClick={() => handleStrategyToggle(strategy.name)}
                      disabled={isLoading}
                      aria-pressed={isSelected}
                      className={cn(
                        'relative text-left bg-background border border-border rounded-lg p-3.5 cursor-pointer transition-all duration-150',
                        'hover:border-muted-foreground/50 hover:bg-accent/5',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                        'disabled:pointer-events-none disabled:opacity-50',
                        isSelected && 'border-primary bg-primary/5 ring-1 ring-primary',
                      )}
                    >
                      {/* Check indicator */}
                      <span
                        className={cn(
                          'absolute top-2.5 right-2.5 flex h-[18px] w-[18px] items-center justify-center rounded-full border border-border transition-all duration-150',
                          isSelected && 'bg-primary border-primary',
                        )}
                        aria-hidden="true"
                      >
                        <Check
                          className={cn(
                            'h-2.5 w-2.5 text-primary-foreground transition-opacity duration-150',
                            isSelected ? 'opacity-100' : 'opacity-0',
                          )}
                          strokeWidth={2.5}
                        />
                      </span>

                      {/* Category tag with volatility dot */}
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span
                          className={cn(
                            'h-1.5 w-1.5 rounded-full flex-shrink-0',
                            volatilityDotClass[strategy.volatility],
                          )}
                          aria-hidden="true"
                        />
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                          {categoryLabel[strategy.category]}
                        </span>
                      </div>

                      {/* Strategy name */}
                      <p className="text-sm font-semibold leading-snug pr-6 mb-1">
                        {strategy.label}
                      </p>

                      {/* Description */}
                      <p
                        className={cn(
                          'text-[11px] leading-relaxed',
                          isSelected ? 'text-muted-foreground' : 'text-muted-foreground/70',
                        )}
                      >
                        {strategy.description}
                      </p>
                    </button>
                  );
                })}
              </div>

              {selectedStrategies.length >= 2 && (
                <p className="text-xs text-muted-foreground px-3 py-2 bg-primary/5 rounded-md border border-primary/10">
                  <span className="font-medium text-primary">Comparison mode</span> — Each selected
                  strategy will run as a separate simulation for direct comparison.
                </p>
              )}
              {selectedStrategies.length === 0 && (
                <p className="text-xs text-destructive">
                  Select at least one strategy to continue.
                </p>
              )}
            </div>

            {/* Constraints — shown when any non-"none" strategy is selected */}
            {hasNonNoneStrategy && (
              <>
                <div className="border-t border-border pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Constraints
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="arena-max-per-sector">Max Per Sector</Label>
                      <Input
                        id="arena-max-per-sector"
                        type="number"
                        min="1"
                        value={maxPerSector}
                        onChange={(e) => setMaxPerSector(e.target.value)}
                        className="mt-1"
                        disabled={isLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        Limit positions in any single sector
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="arena-max-open-positions">Max Open Positions</Label>
                      <Input
                        id="arena-max-open-positions"
                        type="number"
                        min="1"
                        value={maxOpenPositions}
                        placeholder="Unlimited"
                        onChange={(e) => setMaxOpenPositions(e.target.value)}
                        className="mt-1"
                        disabled={isLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        Total simultaneous open positions
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Advanced Tuning — collapsible, only shown for multi-factor strategies */}
            {hasEnrichedScoreStrategy && (
              <div className="border-t border-border pt-4">
                <button
                  type="button"
                  onClick={() => setAdvancedOpen((prev) => !prev)}
                  className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors duration-150 py-1"
                  aria-expanded={advancedOpen}
                >
                  <ChevronRight
                    className={cn(
                      'h-3.5 w-3.5 transition-transform duration-200',
                      advancedOpen && 'rotate-90',
                    )}
                  />
                  Advanced Tuning
                </button>

                {advancedOpen && (
                  <div className="pt-3 grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="arena-ma-sweet-spot-center">
                        Ideal Pullback Depth (%)
                      </Label>
                      <Input
                        id="arena-ma-sweet-spot-center"
                        type="number"
                        min="0.1"
                        step="0.5"
                        value={maSweetSpotCenter}
                        onChange={(e) => setMaSweetSpotCenter(e.target.value)}
                        className="mt-1"
                        disabled={isLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        How far below the 20-day moving average is the ideal entry zone (default:
                        8.5%)
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="border-t border-border pt-4">
              <button
                type="button"
                onClick={() => setEntryFiltersOpen((prev) => !prev)}
                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors duration-150 py-1"
                aria-expanded={entryFiltersOpen}
                aria-controls="arena-entry-filters-panel"
              >
                <ChevronRight
                  className={cn(
                    'h-3.5 w-3.5 transition-transform duration-200',
                    entryFiltersOpen && 'rotate-90',
                  )}
                />
                Entry Filters
              </button>

              {entryFiltersOpen && (
                <div id="arena-entry-filters-panel" className="pt-3 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="arena-ibs-threshold">IBS Threshold</Label>
                      <Input
                        id="arena-ibs-threshold"
                        type="number"
                        min="0.01"
                        max="1"
                        step="0.05"
                        placeholder="Disabled"
                        value={ibsMaxThreshold}
                        onChange={(e) => setIbsMaxThreshold(e.target.value)}
                        className="mt-1"
                        disabled={isLoading}
                      />
                      {hasIbsError && (
                        <p className="text-xs text-destructive">
                          Must be greater than 0 and at most 1
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        Filter entries when close is near daily high. Typical: 0.55. Empty = disabled.
                      </p>
                    </div>
                  </div>

                  {/* MA50 Filter toggle */}
                  <div className="space-y-2">
                    <Label>MA50 Filter</Label>
                    <button
                      type="button"
                      onClick={() => setMa50FilterEnabled((prev) => !prev)}
                      disabled={isLoading}
                      aria-pressed={ma50FilterEnabled}
                      className={cn(
                        'px-3 py-1.5 text-sm rounded border transition-all duration-150',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                        'disabled:pointer-events-none disabled:opacity-50',
                        ma50FilterEnabled
                          ? 'border-primary bg-primary/10 text-primary font-medium'
                          : 'border-border bg-background text-muted-foreground hover:border-muted-foreground/50',
                      )}
                      data-testid="ma50-filter-toggle"
                    >
                      MA50 Filter: {ma50FilterEnabled ? 'On' : 'Off'}
                    </button>
                    <p className="text-xs text-muted-foreground">
                      Only buy stocks trading above their 50-day moving average. Inactive for symbols with &lt;50 bars of history.
                    </p>
                  </div>

                  {/* Circuit Breaker */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="arena-cb-threshold">Market ATR% Threshold</Label>
                      <Input
                        id="arena-cb-threshold"
                        type="number"
                        min="0.01"
                        step="0.1"
                        placeholder="Disabled"
                        value={circuitBreakerThreshold}
                        onChange={(e) => setCircuitBreakerThreshold(e.target.value)}
                        className="mt-1"
                        disabled={isLoading}
                      />
                      {hasCbThresholdError && (
                        <p className="text-xs text-destructive">
                          Must be a positive number
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        Block all entries when market ATR% &ge; threshold. e.g. 2.8 for 2.8%. Empty = disabled.
                      </p>
                    </div>

                    {circuitBreakerThreshold !== '' && (
                      <div className="space-y-2">
                        <Label htmlFor="arena-cb-symbol">Market Symbol</Label>
                        <Input
                          id="arena-cb-symbol"
                          type="text"
                          placeholder="SPY"
                          value={circuitBreakerSymbol}
                          onChange={(e) => setCircuitBreakerSymbol(e.target.value.toUpperCase())}
                          className="mt-1"
                          disabled={isLoading}
                          maxLength={5}
                        />
                        {hasCbSymbolError && (
                          <p className="text-xs text-destructive">
                            {cbSymbolErrorMessage}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground">
                          Ticker used to measure market volatility. Default: SPY.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Submit Button — always visible outside the tab panels */}
        <Button onClick={handleSubmit} disabled={!canSubmit} className="w-full" size="lg">
          <Play className="h-4 w-4 mr-2" />
          {submitButtonLabel}
        </Button>
      </CardContent>
    </Card>
  );
};
