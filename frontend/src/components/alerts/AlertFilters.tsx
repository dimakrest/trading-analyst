import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Label } from '../ui/label'

const FIBONACCI_STATUSES = [
  { value: 'no_structure', label: 'No Structure' },
  { value: 'rallying', label: 'Rallying' },
  { value: 'pullback_started', label: 'Pullback' },
  { value: 'retracing', label: 'Retracing' },
  { value: 'at_level', label: 'At Level' },
  { value: 'bouncing', label: 'Bouncing' },
  { value: 'invalidated', label: 'Invalidated' },
]

const MA_STATUSES = [
  { value: 'above_ma', label: 'Above MA' },
  { value: 'approaching', label: 'Approaching' },
  { value: 'at_ma', label: 'At MA' },
  { value: 'below_ma', label: 'Below MA' },
  { value: 'insufficient_data', label: 'No Data' },
]

const ALL_STATUSES = [...FIBONACCI_STATUSES, ...MA_STATUSES]

interface AlertFiltersProps {
  alertType: string
  status: string
  onAlertTypeChange: (value: string) => void
  onStatusChange: (value: string) => void
}

/**
 * Filter controls for the alerts dashboard
 *
 * Provides alert type and status dropdowns. Status options adapt
 * to the selected alert type to show only relevant statuses.
 */
export function AlertFilters({ alertType, status, onAlertTypeChange, onStatusChange }: AlertFiltersProps) {
  const statusOptionsForType = (type: string): typeof ALL_STATUSES => {
    if (type === 'fibonacci') return FIBONACCI_STATUSES
    if (type === 'moving_average') return MA_STATUSES
    return ALL_STATUSES
  }

  const statusOptions = statusOptionsForType(alertType)

  // Reset status when type changes if current status is not in the new list
  const handleAlertTypeChange = (value: string) => {
    onAlertTypeChange(value)
    const validStatuses = statusOptionsForType(value)
    const isStatusValid = value === 'all' || validStatuses.some((s) => s.value === status)
    if (!isStatusValid) {
      onStatusChange('all')
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-2">
        <Label className="text-xs text-text-muted whitespace-nowrap">Type</Label>
        <Select value={alertType} onValueChange={handleAlertTypeChange}>
          <SelectTrigger className="h-8 w-[160px] text-xs bg-bg-secondary border-default">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="fibonacci">Fibonacci</SelectItem>
            <SelectItem value="moving_average">Moving Average</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <Label className="text-xs text-text-muted whitespace-nowrap">Status</Label>
        <Select value={status} onValueChange={onStatusChange}>
          <SelectTrigger className="h-8 w-[160px] text-xs bg-bg-secondary border-default">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {statusOptions.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
