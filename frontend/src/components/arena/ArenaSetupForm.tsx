/**
 * Arena Setup Form
 *
 * Form for configuring and starting a new trading simulation.
 * Supports symbol input, date range, capital settings, and portfolio setup selection.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Play } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { ListSelector } from '../molecules/ListSelector';
import { useStockLists } from '../../hooks/useStockLists';
import { useAgentConfigs } from '../../hooks/useAgentConfigs';
import { usePortfolioConfigs } from '../../hooks/usePortfolioConfigs';
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
    stock_list_id?: number | null;
    stock_list_name?: string | null;
    agent_config_id?: number | null;
    portfolio_config_id?: number | null;
  };
}

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
 * Arena Setup Form Component
 *
 * Features:
 * - Multi-line textarea for symbols (comma, space, or newline separated)
 * - Date range picker (start and end dates)
 * - Capital settings
 * - Portfolio setup selection (strategy, position size, min score, and stop loss)
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
  const [selectedListId, setSelectedListId] = useState<number | null>(null);
  const [selectedPortfolioConfigId, setSelectedPortfolioConfigId] = useState<number | null>(null);
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

  // Fetch portfolio configs
  const {
    configs: portfolioConfigs,
    isLoading: portfolioConfigsLoading,
    error: portfolioConfigsError,
  } = usePortfolioConfigs();
  const selectedPortfolioConfig = portfolioConfigs.find((c) => c.id === selectedPortfolioConfigId);

  // Show toast if configs fail to load
  useEffect(() => {
    if (agentConfigsError) {
      toast.error(agentConfigsError);
    }
  }, [agentConfigsError]);

  // Show toast if portfolio configs fail to load
  useEffect(() => {
    if (portfolioConfigsError) {
      toast.error(portfolioConfigsError);
    }
  }, [portfolioConfigsError]);

  // Populate form when initialValues are provided (e.g., from replay)
  useEffect(() => {
    if (initialValues) {
      setSymbols(initialValues.symbols.join(', '));
      setStartDate(initialValues.start_date);
      setEndDate(initialValues.end_date);
      setCapital(initialValues.initial_capital.toString());
      // Always set list ID (including null for custom symbols)
      setSelectedListId(initialValues.stock_list_id ?? null);
      // Set agent config ID from replay if available
      if (initialValues.agent_config_id) {
        setSelectedAgentConfigId(initialValues.agent_config_id);
      }
      // Set portfolio setup ID if available
      if (initialValues.portfolio_config_id != null) {
        setSelectedPortfolioConfigId(initialValues.portfolio_config_id);
      }
      // Focus textarea after population
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }, [initialValues]);

  // Auto-select first setup to keep arena configuration fully portfolio-driven.
  useEffect(() => {
    if (selectedPortfolioConfigId !== null) return;
    if (portfolioConfigs.length === 0) return;
    setSelectedPortfolioConfigId(portfolioConfigs[0].id);
  }, [portfolioConfigs, selectedPortfolioConfigId]);

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
    if (symbolList.length === 0 || selectedPortfolioConfigId === null) return;

    await onSubmit({
      symbols: symbolList,
      start_date: startDate,
      end_date: endDate,
      initial_capital: parseFloat(capital),
      stock_list_id: selectedList?.id,
      stock_list_name: selectedList?.name,
      agent_config_id: selectedAgentConfigId,
      portfolio_config_id: selectedPortfolioConfigId,
    });
  }, [symbols, startDate, endDate, capital, selectedList, selectedAgentConfigId, selectedPortfolioConfigId, onSubmit]);

  const symbolList = parseSymbols(symbols);
  const hasValidSymbols = symbolList.length > 0 && symbolList.length <= MAX_ARENA_SYMBOLS;
  const hasValidDates = startDate && endDate && new Date(startDate) < new Date(endDate);
  const hasValidCapital = parseFloat(capital) > 0;
  const hasSelectedPortfolioSetup = selectedPortfolioConfigId !== null;

  const canSubmit =
    hasValidSymbols &&
    hasValidDates &&
    hasValidCapital &&
    hasSelectedPortfolioSetup &&
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
        <div>
          <Label htmlFor="arena-capital">Capital ($)</Label>
          <Input
            id="arena-capital"
            type="number"
            min="1"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            className="mt-1 max-w-xs"
            disabled={isLoading}
          />
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
          <p className="text-xs text-muted-foreground">
            Stop loss, position sizing, score threshold, and portfolio strategy are controlled by
            the selected portfolio setup.
          </p>
        </div>

        {/* Portfolio Setup Selection */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium">Portfolio Setup</h3>

          <div className="space-y-2">
            <Label htmlFor="arena-portfolio-setup">Saved Setup</Label>
            <Select
              value={selectedPortfolioConfigId?.toString() ?? '__none__'}
              onValueChange={(value) => {
                if (value === '__none__') return;
                setSelectedPortfolioConfigId(Number(value));
              }}
              disabled={portfolioConfigsLoading || isLoading}
            >
              <SelectTrigger id="arena-portfolio-setup">
                <SelectValue placeholder="Select portfolio setup..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__" disabled>
                  Select portfolio setup...
                </SelectItem>
                {portfolioConfigs.length > 0 ? (
                  portfolioConfigs.map((config) => (
                    <SelectItem key={config.id} value={config.id.toString()}>
                      {config.name}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="no-setups" disabled>
                    No portfolio setups available
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {selectedPortfolioConfig
                ? `Using "${selectedPortfolioConfig.name}" — Strategy: ${selectedPortfolioConfig.portfolio_strategy}, Size: $${selectedPortfolioConfig.position_size}, Min score: ${selectedPortfolioConfig.min_buy_score}, Stop: ${selectedPortfolioConfig.trailing_stop_pct}%`
                : 'Create setups in the Portfolios page to run Arena simulations'}
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
