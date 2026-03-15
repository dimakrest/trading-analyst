import { Badge } from '../ui/badge'
import { ALERT_STATUS_COLORS } from '../../constants/colors'

const STATUS_LABELS: Record<string, string> = {
  no_structure: 'No Structure',
  rallying: 'Rallying',
  pullback_started: 'Pullback',
  retracing: 'Retracing',
  at_level: 'At Level',
  bouncing: 'Bouncing',
  invalidated: 'Invalidated',
  above_ma: 'Above MA',
  approaching: 'Approaching',
  at_ma: 'At MA',
  below_ma: 'Below MA',
  insufficient_data: 'No Data',
}

interface AlertStatusBadgeProps {
  status: string
}

/**
 * Badge component that maps alert status strings to colored Badge variants
 *
 * Actionable statuses (at_level, at_ma) pulse to draw attention.
 */
export function AlertStatusBadge({ status }: AlertStatusBadgeProps) {
  const colorClass = ALERT_STATUS_COLORS[status] ?? 'bg-text-muted/10 text-text-muted/60 border border-text-muted/20'
  const label = STATUS_LABELS[status] ?? status

  return (
    <Badge className={colorClass}>
      {label}
    </Badge>
  )
}
