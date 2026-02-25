/**
 * Setup Simulation Form
 *
 * Allows the user to define multiple trading setups and an end date,
 * then submit for simulation. Each row represents one setup with its own
 * symbol, entry price, stop loss, trailing stop %, and start date.
 */
import { useId, useState } from 'react';
import { Play, Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { RunSetupSimulationRequest } from '@/types/setupSim';

interface SetupFormRow {
  symbol: string;
  entry_price: string;
  stop_loss_day1: string;
  trailing_stop_pct: string;
  start_date: string;
}

const emptyRow = (): SetupFormRow => ({
  symbol: '',
  entry_price: '',
  stop_loss_day1: '',
  trailing_stop_pct: '',
  start_date: '',
});

interface SetupSimFormProps {
  onSubmit: (request: RunSetupSimulationRequest) => void;
  isLoading: boolean;
}

/**
 * Validate a single setup row against all business rules.
 * Returns true only when the row is completely valid.
 */
const isRowValid = (row: SetupFormRow, endDate: string): boolean => {
  if (!row.symbol.trim()) return false;

  const entry = parseFloat(row.entry_price);
  const stop = parseFloat(row.stop_loss_day1);
  const trailingPct = parseFloat(row.trailing_stop_pct);

  if (!isFinite(entry) || entry <= 0) return false;
  if (!isFinite(stop) || stop <= 0 || stop >= entry) return false;
  if (!isFinite(trailingPct) || trailingPct <= 0 || trailingPct >= 100) return false;
  if (!row.start_date) return false;
  if (endDate && row.start_date >= endDate) return false;

  return true;
};

/**
 * Validate end date: must be set and not in the future.
 */
const isEndDateValid = (endDate: string): boolean => {
  if (!endDate) return false;
  const today = new Date().toISOString().split('T')[0];
  return endDate <= today;
};

export const SetupSimForm = ({ onSubmit, isLoading }: SetupSimFormProps) => {
  const formId = useId();
  const [rows, setRows] = useState<SetupFormRow[]>([emptyRow()]);
  const [endDate, setEndDate] = useState('');

  const handleRowChange = (
    index: number,
    field: keyof SetupFormRow,
    value: string,
  ) => {
    setRows((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: field === 'symbol' ? value.toUpperCase() : value };
      return next;
    });
  };

  const handleAddRow = () => {
    setRows((prev) => [...prev, emptyRow()]);
  };

  const handleRemoveRow = (index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    onSubmit({
      setups: rows.map((row) => ({
        symbol: row.symbol.trim().toUpperCase(),
        entry_price: row.entry_price,
        stop_loss_day1: row.stop_loss_day1,
        trailing_stop_pct: row.trailing_stop_pct,
        start_date: row.start_date,
      })),
      end_date: endDate,
    });
  };

  const endDateValid = isEndDateValid(endDate);
  const allRowsValid = rows.length > 0 && rows.every((row) => isRowValid(row, endDate));
  const canSubmit = endDateValid && allRowsValid && !isLoading;

  const today = new Date().toISOString().split('T')[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Setup Simulation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* End Date */}
        <div className="max-w-xs">
          <Label htmlFor={`${formId}-end-date`}>End Date</Label>
          <Input
            id={`${formId}-end-date`}
            type="date"
            value={endDate}
            max={today}
            onChange={(e) => setEndDate(e.target.value)}
            className="mt-1"
            disabled={isLoading}
          />
          <p className="text-xs text-muted-foreground mt-1">
            Simulation runs through this date (cannot be in the future)
          </p>
        </div>

        {/* Setup Rows */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Setups</h3>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddRow}
              disabled={isLoading}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Setup
            </Button>
          </div>

          {rows.map((row, index) => (
            <div
              key={index}
              className="rounded-lg border border-border p-4 space-y-3"
              data-testid={`setup-row-${index}`}
            >
              {/* Row header with remove button */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                  Setup {index + 1}
                </span>
                {rows.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleRemoveRow(index)}
                    disabled={isLoading}
                    aria-label={`Remove setup ${index + 1}`}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {/* Row fields */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {/* Symbol */}
                <div>
                  <Label htmlFor={`${formId}-symbol-${index}`} className="text-xs">
                    Symbol
                  </Label>
                  <Input
                    id={`${formId}-symbol-${index}`}
                    type="text"
                    placeholder="AAPL"
                    value={row.symbol}
                    onChange={(e) => handleRowChange(index, 'symbol', e.target.value)}
                    className="mt-1 font-mono uppercase"
                    disabled={isLoading}
                    maxLength={10}
                  />
                </div>

                {/* Start Date */}
                <div>
                  <Label htmlFor={`${formId}-start-date-${index}`} className="text-xs">
                    Start Date
                  </Label>
                  <Input
                    id={`${formId}-start-date-${index}`}
                    type="date"
                    value={row.start_date}
                    max={endDate || today}
                    onChange={(e) => handleRowChange(index, 'start_date', e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>

                {/* Entry Price */}
                <div>
                  <Label htmlFor={`${formId}-entry-${index}`} className="text-xs">
                    Entry Price ($)
                  </Label>
                  <Input
                    id={`${formId}-entry-${index}`}
                    type="number"
                    placeholder="150.00"
                    min="0.01"
                    step="0.01"
                    value={row.entry_price}
                    onChange={(e) => handleRowChange(index, 'entry_price', e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>

                {/* Stop Loss Day 1 */}
                <div>
                  <Label htmlFor={`${formId}-stop-${index}`} className="text-xs">
                    Stop Loss Day 1 ($)
                  </Label>
                  <Input
                    id={`${formId}-stop-${index}`}
                    type="number"
                    placeholder="145.00"
                    min="0.01"
                    step="0.01"
                    value={row.stop_loss_day1}
                    onChange={(e) => handleRowChange(index, 'stop_loss_day1', e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                  {row.stop_loss_day1 && row.entry_price &&
                    parseFloat(row.stop_loss_day1) >= parseFloat(row.entry_price) && (
                      <p className="text-xs text-destructive mt-1">Must be below entry price</p>
                    )}
                </div>

                {/* Trailing Stop % */}
                <div>
                  <Label htmlFor={`${formId}-trailing-${index}`} className="text-xs">
                    Trailing Stop (%)
                  </Label>
                  <Input
                    id={`${formId}-trailing-${index}`}
                    type="number"
                    placeholder="5"
                    min="0.01"
                    max="99.99"
                    step="0.5"
                    value={row.trailing_stop_pct}
                    onChange={(e) => handleRowChange(index, 'trailing_stop_pct', e.target.value)}
                    className="mt-1"
                    disabled={isLoading}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Submit */}
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="w-full"
          size="lg"
          data-testid="run-simulation-btn"
        >
          <Play className="h-4 w-4 mr-2" />
          {isLoading ? 'Running...' : 'Run Simulation'}
        </Button>
      </CardContent>
    </Card>
  );
};
