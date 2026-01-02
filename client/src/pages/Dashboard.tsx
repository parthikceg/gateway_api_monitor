import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle, Database, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api, type Change } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

interface Stats {
  totalChanges: number
  highSeverity: number
  recentSnapshots: number
  tiersMonitored: string[]
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats>({
    totalChanges: 0,
    highSeverity: 0,
    recentSnapshots: 0,
    tiersMonitored: ['stable', 'preview', 'beta'],
  })
  const [recentChanges, setRecentChanges] = useState<Change[]>([])
  const [loading, setLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const [changesRes, snapshotsRes] = await Promise.all([
        api.getChanges({ limit: 50 }),
        api.getSnapshotStats(),
      ])

      const changes = changesRes.changes
      const highSeverityCount = changes.filter(c => c.severity === 'high').length
      const totalSnapshots = snapshotsRes.stats.reduce((acc, s) => acc + s.count, 0)

      setStats({
        totalChanges: changes.length,
        highSeverity: highSeverityCount,
        recentSnapshots: totalSnapshots,
        tiersMonitored: ['stable', 'preview', 'beta'],
      })

      setRecentChanges(changes.slice(0, 5))
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleRunMonitoring() {
    setIsRunning(true)
    try {
      await api.runMonitoring()
      await loadData()
    } catch (error) {
      console.error('Failed to run monitoring:', error)
    } finally {
      setIsRunning(false)
    }
  }

  const getSeverityVariant = (severity: string) => {
    switch (severity) {
      case 'high': return 'high'
      case 'medium': return 'medium'
      case 'low': return 'low'
      default: return 'info'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Overview</h2>
          <p className="text-muted-foreground">Monitor Stripe API changes in real-time</p>
        </div>
        <Button onClick={handleRunMonitoring} disabled={isRunning}>
          {isRunning ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
              Running...
            </>
          ) : (
            <>
              <Activity className="h-4 w-4 mr-2" />
              Run Monitoring
            </>
          )}
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Changes</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalChanges}</div>
            <p className="text-xs text-muted-foreground">Detected across all tiers</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High Severity</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.highSeverity}</div>
            <p className="text-xs text-muted-foreground">Breaking or critical changes</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Snapshots</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.recentSnapshots}</div>
            <p className="text-xs text-muted-foreground">API snapshots captured</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tiers Monitored</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="flex gap-1">
              <Badge variant="stable">Stable</Badge>
              <Badge variant="preview">Preview</Badge>
              <Badge variant="beta">Beta</Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Changes</CardTitle>
            <CardDescription>Latest API changes detected</CardDescription>
          </CardHeader>
          <CardContent>
            {recentChanges.length === 0 ? (
              <p className="text-sm text-muted-foreground">No changes detected yet. Run monitoring to start tracking.</p>
            ) : (
              <div className="space-y-3">
                {recentChanges.map((change) => (
                  <div key={change.id} className="flex items-start gap-3 p-3 rounded-lg border">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={getSeverityVariant(change.severity)} className="capitalize">
                          {change.severity}
                        </Badge>
                        <Badge variant={change.tier as 'stable' | 'preview' | 'beta'} className="capitalize">
                          {change.tier}
                        </Badge>
                      </div>
                      <p className="text-sm font-medium truncate">{change.field}</p>
                      <p className="text-xs text-muted-foreground">{change.type}</p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(change.detected_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API Coverage</CardTitle>
            <CardDescription>Currently monitored endpoints</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-lg border">
                <div>
                  <p className="font-medium">Payment Intents</p>
                  <p className="text-sm text-muted-foreground">Stripe</p>
                </div>
                <Badge variant="stable">Active</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border opacity-50">
                <div>
                  <p className="font-medium">Checkout Sessions</p>
                  <p className="text-sm text-muted-foreground">Stripe</p>
                </div>
                <Badge variant="secondary">Coming Soon</Badge>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg border opacity-50">
                <div>
                  <p className="font-medium">Transactions</p>
                  <p className="text-sm text-muted-foreground">Braintree</p>
                </div>
                <Badge variant="secondary">Coming Soon</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
