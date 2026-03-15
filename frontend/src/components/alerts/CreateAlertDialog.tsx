import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { ToggleGroup, ToggleGroupItem } from '../ui/toggle-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import type { StockAlert, CreateAlertRequest } from '../../types/alert'

/** Fibonacci retracement level options as decimals */
const FIB_LEVELS = [
  { value: 0.236, label: '23.6%' },
  { value: 0.382, label: '38.2%' },
  { value: 0.5, label: '50%' },
  { value: 0.618, label: '61.8%' },
  { value: 0.786, label: '78.6%' },
]

const DEFAULT_FIB_LEVELS = [0.382, 0.5, 0.618]

/** Moving average period options */
const MA_PERIODS = [
  { value: 20, label: 'MA20' },
  { value: 50, label: 'MA50' },
  { value: 150, label: 'MA150' },
  { value: 200, label: 'MA200' },
]

const DEFAULT_MA_PERIODS = [50]

interface CreateAlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: CreateAlertRequest) => Promise<StockAlert[]>
  onFirstCreate?: () => void
  isSubmitting?: boolean
}

/**
 * Dialog for creating Fibonacci retracement or Moving Average alerts.
 *
 * On the first alert creation it calls onFirstCreate so the parent can
 * request browser notification permission.
 */
export function CreateAlertDialog({
  open,
  onOpenChange,
  onSubmit,
  onFirstCreate,
  isSubmitting = false,
}: CreateAlertDialogProps) {
  const [symbol, setSymbol] = useState('')
  const [alertType, setAlertType] = useState<'fibonacci' | 'moving_average'>('fibonacci')

  // Fibonacci state
  const [selectedFibLevels, setSelectedFibLevels] = useState<number[]>(DEFAULT_FIB_LEVELS)

  // Moving average state
  const [selectedMaPeriods, setSelectedMaPeriods] = useState<number[]>(DEFAULT_MA_PERIODS)
  const [maDirection, setMaDirection] = useState<'above' | 'below' | 'both'>('both')

  // Tolerance (advanced / collapsed section)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [tolerancePct, setTolerancePct] = useState('0.5')

  const [error, setError] = useState<string | null>(null)

  const toggleFibLevel = (level: number) => {
    setSelectedFibLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    )
  }

  const toggleMaPeriod = (period: number) => {
    setSelectedMaPeriods((prev) =>
      prev.includes(period) ? prev.filter((p) => p !== period) : [...prev, period]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmedSymbol = symbol.trim().toUpperCase()
    if (!trimmedSymbol) {
      setError('Symbol is required')
      return
    }

    if (alertType === 'fibonacci' && selectedFibLevels.length === 0) {
      setError('Select at least one Fibonacci level')
      return
    }

    if (alertType === 'moving_average' && selectedMaPeriods.length === 0) {
      setError('Select at least one moving average period')
      return
    }

    const parsedTolerance = parseFloat(tolerancePct)
    if (isNaN(parsedTolerance) || parsedTolerance < 0) {
      setError('Tolerance must be a positive number')
      return
    }

    const request: CreateAlertRequest =
      alertType === 'fibonacci'
        ? {
            symbol: trimmedSymbol,
            alert_type: 'fibonacci',
            config: {
              levels: [...selectedFibLevels].sort((a, b) => a - b),
              tolerance_pct: parsedTolerance,
              min_swing_pct: 5,
            },
          }
        : {
            symbol: trimmedSymbol,
            alert_type: 'moving_average',
            config: {
              ma_periods: [...selectedMaPeriods].sort((a, b) => a - b),
              tolerance_pct: parsedTolerance,
              direction: maDirection,
            },
          }

    try {
      await onSubmit(request)
      onFirstCreate?.()
      handleReset()
      onOpenChange(false)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create alert'
      setError(msg)
    }
  }

  const handleReset = () => {
    setSymbol('')
    setAlertType('fibonacci')
    setSelectedFibLevels(DEFAULT_FIB_LEVELS)
    setSelectedMaPeriods(DEFAULT_MA_PERIODS)
    setMaDirection('both')
    setTolerancePct('0.5')
    setShowAdvanced(false)
    setError(null)
  }

  const handleCancel = () => {
    handleReset()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-bg-secondary border-default">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-semibold text-text-primary">
            Add Alert
          </DialogTitle>
          <DialogDescription className="text-sm text-text-muted">
            Monitor a stock for Fibonacci retracement levels or moving average crossings
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            {/* Symbol input */}
            <div className="space-y-2">
              <Label
                htmlFor="alert-symbol"
                className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
              >
                Symbol
              </Label>
              <Input
                id="alert-symbol"
                placeholder="e.g., AAPL"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                disabled={isSubmitting}
                autoFocus
                autoComplete="off"
                className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted font-mono"
              />
            </div>

            {/* Alert type selector */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                Alert Type
              </Label>
              <ToggleGroup
                type="single"
                value={alertType}
                onValueChange={(value) =>
                  value && setAlertType(value as 'fibonacci' | 'moving_average')
                }
                disabled={isSubmitting}
                className="justify-start gap-2"
              >
                <ToggleGroupItem
                  value="fibonacci"
                  aria-label="Fibonacci retracement alert"
                  className="flex-1 data-[state=on]:bg-accent-primary data-[state=on]:text-white"
                >
                  Fibonacci
                </ToggleGroupItem>
                <ToggleGroupItem
                  value="moving_average"
                  aria-label="Moving average alert"
                  className="flex-1 data-[state=on]:bg-accent-primary data-[state=on]:text-white"
                >
                  Moving Average
                </ToggleGroupItem>
              </ToggleGroup>
            </div>

            {/* Fibonacci config */}
            {alertType === 'fibonacci' && (
              <div className="space-y-2">
                <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                  Retracement Levels
                </Label>
                <div className="flex flex-wrap gap-2">
                  {FIB_LEVELS.map(({ value, label }) => {
                    const checked = selectedFibLevels.includes(value)
                    return (
                      <button
                        key={value}
                        type="button"
                        role="checkbox"
                        aria-checked={checked}
                        disabled={isSubmitting}
                        onClick={() => toggleFibLevel(value)}
                        className={`px-3 py-1.5 rounded-md border text-xs font-mono transition-colors ${
                          checked
                            ? 'bg-accent-primary/20 border-accent-primary text-accent-primary'
                            : 'bg-bg-tertiary border-default text-text-muted hover:border-accent-primary/50'
                        } disabled:opacity-50`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
                {selectedFibLevels.length === 0 && (
                  <p className="text-xs text-accent-bearish">Select at least one level</p>
                )}
              </div>
            )}

            {/* Moving average config */}
            {alertType === 'moving_average' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted">
                    MA Periods
                  </Label>
                  <div className="flex flex-wrap gap-2">
                    {MA_PERIODS.map(({ value, label }) => {
                      const checked = selectedMaPeriods.includes(value)
                      return (
                        <button
                          key={value}
                          type="button"
                          role="checkbox"
                          aria-checked={checked}
                          disabled={isSubmitting}
                          onClick={() => toggleMaPeriod(value)}
                          className={`px-3 py-1.5 rounded-md border text-xs font-mono transition-colors ${
                            checked
                              ? 'bg-accent-primary/20 border-accent-primary text-accent-primary'
                              : 'bg-bg-tertiary border-default text-text-muted hover:border-accent-primary/50'
                          } disabled:opacity-50`}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                  {selectedMaPeriods.length === 0 && (
                    <p className="text-xs text-accent-bearish">Select at least one period</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label
                    htmlFor="ma-direction"
                    className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
                  >
                    Direction
                  </Label>
                  <Select
                    value={maDirection}
                    onValueChange={(v) => setMaDirection(v as 'above' | 'below' | 'both')}
                    disabled={isSubmitting}
                  >
                    <SelectTrigger
                      id="ma-direction"
                      className="bg-bg-tertiary border-default text-sm"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="both">Both directions</SelectItem>
                      <SelectItem value="above">Alert when above MA</SelectItem>
                      <SelectItem value="below">Alert when below MA</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {/* Advanced settings (tolerance) */}
            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="text-xs text-text-muted hover:text-text-primary transition-colors"
              >
                {showAdvanced ? '▾' : '▸'} Advanced settings
              </button>

              {showAdvanced && (
                <div className="mt-3 space-y-2">
                  <Label
                    htmlFor="tolerance-pct"
                    className="text-xs font-semibold uppercase tracking-[0.06em] text-text-muted"
                  >
                    Tolerance (%)
                  </Label>
                  <Input
                    id="tolerance-pct"
                    type="number"
                    min="0"
                    max="10"
                    step="0.1"
                    value={tolerancePct}
                    onChange={(e) => setTolerancePct(e.target.value)}
                    disabled={isSubmitting}
                    className="bg-bg-tertiary border-default focus:border-accent-primary focus:ring-2 focus:ring-accent-primary-muted w-32"
                  />
                  <p className="text-xs text-text-muted">
                    How close price needs to be before triggering (default: 0.5%)
                  </p>
                </div>
              )}
            </div>

            {/* Error display */}
            {error && (
              <p className="text-sm text-accent-bearish" role="alert">
                {error}
              </p>
            )}
          </div>

          <DialogFooter className="gap-3 border-t border-subtle pt-5">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={isSubmitting}
              className="border-default hover:bg-bg-tertiary"
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Adding...' : 'Add Alert'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
