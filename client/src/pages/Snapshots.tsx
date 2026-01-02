import { useEffect, useState } from 'react'
import { Database, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, type Snapshot } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'

export function Snapshots() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [stats, setStats] = useState<{ tier: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [tierFilter, setTierFilter] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    loadData()
  }, [tierFilter])

  async function loadData() {
    setLoading(true)
    try {
      const params: { limit: number; tier?: string } = { limit: 50 }
      if (tierFilter) params.tier = tierFilter
      
      const [snapshotsRes, statsRes] = await Promise.all([
        api.getSnapshots(params),
        api.getSnapshotStats(),
      ])

      setSnapshots(snapshotsRes.snapshots)
      setStats(statsRes.stats)
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleRefresh() {
    setIsRefreshing(true)
    try {
      await api.runMonitoring()
      await loadData()
    } catch (error) {
      console.error('Failed to refresh:', error)
    } finally {
      setIsRefreshing(false)
    }
  }

  const getTierVariant = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'stable': return 'stable'
      case 'preview': return 'preview'
      case 'beta': return 'beta'
      default: return 'secondary'
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
          <h2 className="text-2xl font-bold">Snapshots</h2>
          <p className="text-muted-foreground">View all captured API snapshots</p>
        </div>
        <Button onClick={handleRefresh} disabled={isRefreshing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
          Capture New Snapshot
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {['stable', 'preview', 'beta'].map((tier) => {
          const stat = stats.find(s => s.tier.toLowerCase() === tier)
          return (
            <Card key={tier}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Badge variant={getTierVariant(tier) as 'stable' | 'preview' | 'beta'} className="capitalize">
                    {tier}
                  </Badge>
                  Snapshots
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat?.count || 0}</div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="flex items-center gap-4">
        <Select value={tierFilter} onValueChange={setTierFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by tier" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All Tiers</SelectItem>
            <SelectItem value="stable">Stable</SelectItem>
            <SelectItem value="preview">Preview</SelectItem>
            <SelectItem value="beta">Beta</SelectItem>
          </SelectContent>
        </Select>

        {tierFilter && (
          <Button variant="ghost" size="sm" onClick={() => setTierFilter('')}>
            Clear filter
          </Button>
        )}
      </div>

      {snapshots.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64">
            <Database className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No snapshots found</p>
            <p className="text-sm text-muted-foreground">Run monitoring to capture API snapshots</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {snapshots.map((snapshot) => (
            <Card key={snapshot.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Database className="h-4 w-4" />
                      {snapshot.endpoint}
                    </CardTitle>
                    <CardDescription>{snapshot.gateway}</CardDescription>
                  </div>
                  <Badge variant={getTierVariant(snapshot.tier) as 'stable' | 'preview' | 'beta'} className="capitalize">
                    {snapshot.tier}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>Captured: {formatDate(snapshot.created_at)}</span>
                  <span>{formatRelativeTime(snapshot.created_at)}</span>
                  <span className="font-mono text-xs">{snapshot.id.slice(0, 8)}...</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
