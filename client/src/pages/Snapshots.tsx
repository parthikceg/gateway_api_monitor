import { useEffect, useState } from 'react'
import { Database, RefreshCw, X, Calendar, Tag, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Snapshot } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'

export function Snapshots() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [stats, setStats] = useState<{ tier: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [tierFilter, setTierFilter] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

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

  async function handleViewSnapshot(snapshot: Snapshot) {
    setDetailLoading(true)
    try {
      const detail = await api.getSnapshotDetail(snapshot.id)
      setSelectedSnapshot(detail)
    } catch (error) {
      console.error('Failed to load snapshot detail:', error)
    } finally {
      setDetailLoading(false)
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
        <Button 
          onClick={handleRefresh} 
          disabled={isRefreshing}
          className="bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
          Capture New Snapshot
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {['stable', 'preview', 'beta'].map((tier) => {
          const stat = stats.find(s => s.tier.toLowerCase() === tier)
          return (
            <Card key={tier} className="stat-card card-hover">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <span className={`badge-${tier} px-2 py-0.5 rounded-full text-xs font-semibold capitalize`}>
                    {tier}
                  </span>
                  Snapshots
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stat?.count || 0}</div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="flex items-center gap-4">
        <Select value={tierFilter || "all"} onValueChange={(value) => setTierFilter(value === "all" ? "" : value)}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by tier" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Tiers</SelectItem>
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
            <Card 
              key={snapshot.id} 
              className="card-hover cursor-pointer transition-all"
              onClick={() => handleViewSnapshot(snapshot)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Database className="h-4 w-4 text-primary" />
                      {snapshot.endpoint}
                    </CardTitle>
                    <CardDescription>{snapshot.gateway}</CardDescription>
                  </div>
                  <span className={`badge-${snapshot.tier.toLowerCase()} px-2.5 py-1 rounded-full text-xs font-semibold capitalize`}>
                    {snapshot.tier}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {formatDate(snapshot.created_at)}
                  </span>
                  <span>{formatRelativeTime(snapshot.created_at)}</span>
                  <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{snapshot.id.slice(0, 8)}...</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!selectedSnapshot} onOpenChange={() => setSelectedSnapshot(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Snapshot Details
            </DialogTitle>
            <DialogDescription>
              Full captured API object data
            </DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : selectedSnapshot && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Endpoint</p>
                  <p className="font-medium">{selectedSnapshot.endpoint}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Gateway</p>
                  <p className="font-medium">{selectedSnapshot.gateway}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Tier</p>
                  <span className={`badge-${selectedSnapshot.tier.toLowerCase()} px-2.5 py-1 rounded-full text-xs font-semibold capitalize`}>
                    {selectedSnapshot.tier}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Captured</p>
                  <p className="font-medium">{formatDate(selectedSnapshot.created_at)}</p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-xs text-muted-foreground mb-1">Snapshot ID</p>
                <p className="font-mono text-sm">{selectedSnapshot.id}</p>
              </div>

              {selectedSnapshot.spec_url && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Spec URL</p>
                  <a 
                    href={selectedSnapshot.spec_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline flex items-center gap-1"
                  >
                    {selectedSnapshot.spec_url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              <div>
                <p className="text-sm font-medium mb-2">Schema Data</p>
                <ScrollArea className="h-[300px] rounded-lg border bg-slate-950 p-4">
                  <pre className="text-xs text-slate-100 font-mono">
                    {JSON.stringify(selectedSnapshot.schema_data, null, 2)}
                  </pre>
                </ScrollArea>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
