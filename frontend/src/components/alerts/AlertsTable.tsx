import { useNavigate } from 'react-router-dom'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table'
import { Card, CardContent } from '../ui/card'
import { AlertStatusBadge } from './AlertStatusBadge'
import { toAlertTableRow } from '../../types/alert'
import type { StockAlert } from '../../types/alert'
import { formatDate } from '../../utils/formatters'

/** Status ordering: actionable states first */
const STATUS_ORDER: Record<string, number> = {
  at_level: 0,
  at_ma: 0,
  approaching: 1,
  pullback_started: 2,
  retracing: 3,
  bouncing: 4,
  rallying: 5,
  above_ma: 6,
  below_ma: 7,
  invalidated: 8,
  no_structure: 9,
  insufficient_data: 10,
}

const sortAlerts = (alerts: StockAlert[]): StockAlert[] =>
  [...alerts].sort((a, b) => {
    const orderA = STATUS_ORDER[a.status] ?? 99
    const orderB = STATUS_ORDER[b.status] ?? 99
    if (orderA !== orderB) return orderA - orderB
    return a.symbol.localeCompare(b.symbol)
  })

interface AlertsTableProps {
  alerts: StockAlert[]
}

/**
 * Renders alert data as a table (desktop) or card list (mobile).
 *
 * Rows are sorted with actionable statuses first. Clicking a row
 * navigates to the alert detail page.
 */
export function AlertsTable({ alerts }: AlertsTableProps) {
  const navigate = useNavigate()
  const sorted = sortAlerts(alerts)
  const rows = sorted.map(toAlertTableRow)

  const handleRowClick = (id: number) => {
    navigate(`/alerts/${id}`)
  }

  // Mobile card layout
  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="border-subtle hover:bg-transparent">
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Symbol
              </TableHead>
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Alert Type
              </TableHead>
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Price
              </TableHead>
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Status
              </TableHead>
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Details
              </TableHead>
              <TableHead className="text-text-muted font-semibold text-xs uppercase tracking-[0.06em]">
                Last Alert
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.id}
                className="border-subtle hover:bg-bg-secondary/50 cursor-pointer transition-colors"
                onClick={() => handleRowClick(row.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleRowClick(row.id)
                  }
                }}
                aria-label={`View details for ${row.symbol} ${row.alertTypeLabel} alert`}
              >
                <TableCell className="font-mono font-semibold text-text-primary">
                  {row.symbol}
                </TableCell>
                <TableCell className="text-text-muted text-sm">
                  {row.alertTypeLabel}
                </TableCell>
                <TableCell className="font-mono text-text-primary">
                  {row.currentPrice != null ? `$${row.currentPrice.toFixed(2)}` : '—'}
                </TableCell>
                <TableCell>
                  <AlertStatusBadge status={row.status} />
                </TableCell>
                <TableCell className="text-text-muted text-sm max-w-[280px] truncate">
                  {row.detailsText}
                </TableCell>
                <TableCell className="text-text-muted text-sm whitespace-nowrap">
                  {row.lastTriggeredAt ? formatDate(row.lastTriggeredAt) : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-2">
        {rows.map((row) => (
          <Card
            key={row.id}
            className="border-default hover:border-accent-primary transition-colors cursor-pointer"
            onClick={() => handleRowClick(row.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                handleRowClick(row.id)
              }
            }}
            aria-label={`View details for ${row.symbol} ${row.alertTypeLabel} alert`}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono font-semibold text-text-primary">
                      {row.symbol}
                    </span>
                    <AlertStatusBadge status={row.status} />
                  </div>
                  <p className="text-xs text-text-muted mb-1">{row.alertTypeLabel}</p>
                  <p className="text-xs text-text-muted truncate">{row.detailsText}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-mono text-sm text-text-primary">
                    {row.currentPrice != null ? `$${row.currentPrice.toFixed(2)}` : '—'}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    {row.lastTriggeredAt ? formatDate(row.lastTriggeredAt) : 'No alerts yet'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}
