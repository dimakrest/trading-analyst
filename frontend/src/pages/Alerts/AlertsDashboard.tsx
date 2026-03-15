import { useState, useMemo } from 'react'
import { Plus, Bell, BellOff, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import { Skeleton } from '../../components/ui/skeleton'
import { AlertsTable } from '../../components/alerts/AlertsTable'
import { AlertFilters } from '../../components/alerts/AlertFilters'
import { CreateAlertDialog } from '../../components/alerts/CreateAlertDialog'
import { useAlertPolling } from '../../hooks/useAlertPolling'
import { useAlerts } from '../../hooks/useAlerts'
import { useNotifications } from '../../hooks/useNotifications'
import type { CreateAlertRequest, StockAlert } from '../../types/alert'

/**
 * Alerts dashboard page
 *
 * Shows all configured stock price alerts with real-time polling.
 * Provides controls to add alerts and filter by type or status.
 */
export function AlertsDashboard() {
  const { alerts, isLoading, error, refetch } = useAlertPolling()
  const { createAlert, isLoading: isMutating } = useAlerts()
  const { permission, requestPermission } = useNotifications()

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [statusAnnouncement, setStatusAnnouncement] = useState('')

  // Track whether user has ever created an alert to trigger permission request once
  const [hasCreatedAlert, setHasCreatedAlert] = useState(false)

  const handleCreate = async (data: CreateAlertRequest): Promise<StockAlert[]> => {
    try {
      const created = await createAlert(data)
      const count = created.length
      toast.success(count === 1 ? `Alert added for ${created[0].symbol}` : `${count} alerts added`)
      setStatusAnnouncement(
        count === 1 ? `Alert added for ${created[0].symbol}` : `${count} alerts added`
      )
      await refetch()
      return created
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create alert'
      toast.error(msg)
      throw err
    }
  }

  const handleFirstCreate = async () => {
    if (!hasCreatedAlert && permission === 'default') {
      setHasCreatedAlert(true)
      await requestPermission()
    }
  }

  // Apply type and status filters client-side
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const typeMatch = filterType === 'all' || alert.alert_type === filterType
      const statusMatch = filterStatus === 'all' || alert.status === filterStatus
      return typeMatch && statusMatch
    })
  }, [alerts, filterType, filterStatus])

  return (
    <div className="flex-1 p-6 flex flex-col gap-5 max-w-[1200px] mx-auto w-full">
      {/* Notification permission banner */}
      {permission === 'granted' && (
        <div
          className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm"
          role="status"
        >
          <Bell className="w-4 h-4 shrink-0" />
          <span>
            Browser notifications are enabled. Keep this tab open to receive alerts.
          </span>
        </div>
      )}

      {permission === 'denied' && (
        <div
          className="flex items-center gap-2 px-4 py-2.5 rounded-md bg-text-muted/5 border border-text-muted/20 text-text-muted text-sm"
          role="status"
        >
          <BellOff className="w-4 h-4 shrink-0" />
          <span>
            Notifications are blocked. Enable them in your browser settings to receive price alerts.
          </span>
        </div>
      )}

      {/* Page header */}
      <div className="flex items-center justify-between gap-6">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-text-primary">
            Alerts
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Monitor stocks for Fibonacci retracement levels and moving average crossings
          </p>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          className="flex items-center gap-2"
          disabled={isLoading}
        >
          <Plus className="w-[18px] h-[18px]" />
          Add Alert
        </Button>
      </div>

      {/* Loading skeleton — shown only on initial fetch */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-md" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <Card className="border-accent-bearish bg-accent-bearish/5">
          <CardContent className="p-6 flex items-start gap-4">
            <div className="flex-1">
              <p className="text-sm text-text-primary font-medium">Failed to load alerts</p>
              <p className="text-sm text-text-muted mt-1">{error}</p>
            </div>
            <Button
              onClick={refetch}
              variant="outline"
              size="sm"
              className="shrink-0 flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Content area — shown once loaded */}
      {!isLoading && !error && (
        <>
          {alerts.length === 0 ? (
            /* Empty state */
            <Card className="border-default">
              <CardContent className="p-10 text-center">
                <Bell className="w-10 h-10 text-text-muted/40 mx-auto mb-3" />
                <p className="text-text-muted">No alerts configured. Add a stock to start monitoring.</p>
                <Button
                  onClick={() => setCreateDialogOpen(true)}
                  className="mt-4"
                  disabled={isMutating}
                >
                  <Plus className="w-4 h-4 mr-1.5" />
                  Add Alert
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Filters row */}
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <AlertFilters
                  alertType={filterType}
                  status={filterStatus}
                  onAlertTypeChange={setFilterType}
                  onStatusChange={setFilterStatus}
                />
                <span className="text-xs text-text-muted">
                  {filteredAlerts.length} of {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Table or empty filtered state */}
              {filteredAlerts.length === 0 ? (
                <div className="py-10 text-center text-text-muted text-sm">
                  No alerts match the current filters.
                </div>
              ) : (
                <AlertsTable alerts={filteredAlerts} />
              )}
            </>
          )}
        </>
      )}

      {/* Accessible live region for status updates */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {statusAnnouncement}
      </div>

      {/* Mutation loading overlay indicator */}
      {isMutating && (
        <div
          className="fixed bottom-6 right-6 flex items-center gap-2 px-3 py-2 rounded-md bg-bg-secondary border border-default shadow-lg text-sm text-text-muted z-50"
          role="status"
          aria-label="Saving..."
        >
          <Loader2 className="w-4 h-4 animate-spin" />
          Saving…
        </div>
      )}

      <CreateAlertDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={handleCreate}
        onFirstCreate={handleFirstCreate}
        isSubmitting={isMutating}
      />
    </div>
  )
}
