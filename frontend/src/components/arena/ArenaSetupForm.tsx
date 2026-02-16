/**
 * Arena Setup Form
 *
 * Form for configuring and starting a new trading simulation.
 * Supports symbol input, date range, capital settings, and trailing stop.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Play } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Slider } from '../ui/slider';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { ListSelector } from '../molecules/ListSelector';
import { useStockLists } from '../../hooks/useStockLists';
import { useAgentConfigs } from '../../hooks/useAgentConfigs';
import type { CreateSimulationRequest } from '../../types/arena';

// Arena configuration constants
const MAX_ARENA_SYMBOLS = 600;

interface ArenaSetupFormProps {
  /** Callback when form is submitted with valid data */
  onSubmit: (request: CreateSimulationRequest) => Promise<void>;
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
 * Get dynamic help text based on minimum buy score and algorithm
 *
 * Shows how many criteria must align for the agent to buy.
 * Context-aware: different text for CCI (multiples of 20) vs RSI-2 (multiples of 5).
 */
const getMinBuyScoreHelpText = (score: number, scoringAlgorithm: 'cci' | 'rsi2' | null): string => {
  if (scoringAlgorithm === 'rsi2') {
    // RSI-2 uses graduated scoring (0/5/10/15/20 per criterion)
    return 'Minimum total score required to trigger a buy signal. With RSI-2, criteria contribute graduated scores (5/10/15/20 pts), so total scores can be any multiple of 5.';
  }

  // CCI uses binary 20-point scoring
  if (score >= 80) {
    return 'Agent buys when at least 4 of 5 criteria align. Each criterion contributes 20 points.';
  }
  if (score >= 60) {
    return 'Agent buys when at least 3 of 5 criteria align. Each criterion contributes 20 points.';
  }
  if (score >= 40) {
    return 'Agent buys when at least 2 of 5 criteria align. Each criterion contributes 20 points.';
  }
  return 'Agent buys when at least 1 of 5 criteria align. Each criterion contributes 20 points.';
};

/**
 * Arena Setup Form Component
 *
 * Features:
 * - Multi-line textarea for symbols (comma, space, or newline separated)
 * - Date range picker (start and end dates)
 * - Capital settings (initial capital and position size)
 * - Trailing stop percentage
 * - Validation: 1-50 symbols, start < end
 * - Submit button with loading state
 */
export const ArenaSetupForm = ({
  onSubmit,
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const handleSubmit = useCallback(async () => {
    const symbolList = parseSymbols(symbols);
    if (symbolList.length === 0) return;

    await onSubmit({
      symbols: symbolList,
      start_date: startDate,
      end_date: endDate,
      initial_capital: parseFloat(capital),
      position_size: parseFloat(positionSize),
      trailing_stop_pct: parseFloat(trailingStopPct),
      min_buy_score: parseFloat(minBuyScore),
      stock_list_id: selectedList?.id,
      stock_list_name: selectedList?.name,
      agent_config_id: selectedAgentConfigId,
    });
  }, [symbols, startDate, endDate, capital, positionSize, trailingStopPct, minBuyScore, selectedList, selectedAgentConfigId, onSubmit]);

  const symbolList = parseSymbols(symbols);
  const hasValidSymbols = symbolList.length > 0 && symbolList.length <= MAX_ARENA_SYMBOLS;
  const hasValidDates = startDate && endDate && new Date(startDate) < new Date(endDate);
  const hasValidCapital = parseFloat(capital) > 0;
  const hasValidPositionSize = parseFloat(positionSize) > 0;
  const hasValidTrailingStop = parseFloat(trailingStopPct) > 0 && parseFloat(trailingStopPct) <= 100;
  const hasValidMinBuyScore = isValidMinBuyScore(parseFloat(minBuyScore));

  const canSubmit =
    hasValidSymbols &&
    hasValidDates &&
    hasValidCapital &&
    hasValidPositionSize &&
    hasValidTrailingStop &&
    hasValidMinBuyScore &&
    !isLoading;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Setup Simulation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
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

        {/* Capital Settings */}
        <div className="grid grid-cols-3 gap-4">
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

        {/* Agent Configuration */}
        <div className="space-y-3">
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="arena-min-buy-score-input">Minimum Buy Score</Label>
              <span className="text-sm font-medium text-muted-foreground">
                {minBuyScore}
              </span>
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
              {getMinBuyScoreHelpText(
                parseFloat(minBuyScore),
                agentConfigs.find((c) => c.id === selectedAgentConfigId)?.scoring_algorithm ?? null
              )}
            </p>
          </div>
        </div>

        {/* Submit Button */}
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="w-full"
          size="lg"
        >
          <Play className="h-4 w-4 mr-2" />
          {isLoading ? 'Creating...' : 'Start Simulation'}
        </Button>
      </CardContent>
    </Card>
  );
};
