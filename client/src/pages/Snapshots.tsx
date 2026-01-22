import { useEffect, useState } from 'react'
import { Database, RefreshCw, Calendar, ExternalLink, Code, Filter } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Snapshot } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'

// Helper to format endpoint path to display name
function formatEndpointName(endpoint: string): string {
  if (!endpoint) return 'Unknown'
  return endpoint
    .replace('/v1/', '')
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function Snapshots() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [stats, setStats] = useState<{ tier: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [tierFilter, setTierFilter] = useState('')
  const [endpointFilter, setEndpointFilter] = useState('')
  const [availableEndpoints, setAvailableEndpoints] = useState<string[]>([])
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    loadEndpoints()
  }, [])

  useEffect(() => {
    loadData()
  }, [tierFilter, endpointFilter])

  async function loadEndpoints() {
    try {
      const res = await api.getEndpoints()
      setAvailableEndpoints(res.endpoints)
    } catch (error) {
      console.error('Failed to load endpoints:', error)
    }
  }

  async function loadData() {
    setLoading(true)
    try {
      const params: { limit: number; tier?: string; endpoint?: string } = { limit: 50 }
      if (tierFilter) params.tier = tierFilter
      if (endpointFilter) params.endpoint = endpointFilter

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

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filters:</span>
        </div>

        <Select value={tierFilter || "all"} onValueChange={(value) => setTierFilter(value === "all" ? "" : value)}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Tier" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Tiers</SelectItem>
            <SelectItem value="stable">Stable</SelectItem>
            <SelectItem value="preview">Preview</SelectItem>
            <SelectItem value="beta">Beta</SelectItem>
          </SelectContent>
        </Select>

        <Select value={endpointFilter || "all"} onValueChange={(value) => setEndpointFilter(value === "all" ? "" : value)}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Endpoint" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Endpoints</SelectItem>
            {availableEndpoints.map((endpoint) => (
              <SelectItem key={endpoint} value={endpoint}>
                {formatEndpointName(endpoint)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {(tierFilter || endpointFilter) && (
          <Button variant="ghost" size="sm" onClick={() => { setTierFilter(''); setEndpointFilter(''); }}>
            Clear filters
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
                      <Code className="h-4 w-4 text-primary" />
                      {formatEndpointName(snapshot.endpoint)}
                    </CardTitle>
                    <CardDescription className="flex items-center gap-2">
                      <span className="font-mono text-xs">{snapshot.endpoint}</span>
                      <span>|</span>
                      <span>{snapshot.gateway}</span>
                    </CardDescription>
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
        <DialogContent className="max-w-3xl h-[90vh] flex flex-col">
          <DialogHeader className="flex-shrink-0">
            <DialogTitle className="flex items-center gap-2">
              <Code className="h-5 w-5 text-primary" />
              {selectedSnapshot ? formatEndpointName(selectedSnapshot.endpoint) : 'Snapshot'} Details
            </DialogTitle>
            <DialogDescription>
              Full captured API schema for {selectedSnapshot?.endpoint || 'this endpoint'}
            </DialogDescription>
          </DialogHeader>

          {detailLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : selectedSnapshot && (
            <div className="flex flex-col min-h-0 flex-1 space-y-4">
              <div className="flex-shrink-0 grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Endpoint</p>
                  <p className="font-medium">{formatEndpointName(selectedSnapshot.endpoint)}</p>
                  <p className="font-mono text-xs text-muted-foreground">{selectedSnapshot.endpoint}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground mb-1">Gateway</p>
                  <p className="font-medium capitalize">{selectedSnapshot.gateway}</p>
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

              <div className="flex-shrink-0 p-3 rounded-lg bg-muted/50">
                <p className="text-xs text-muted-foreground mb-1">Snapshot ID</p>
                <p className="font-mono text-sm">{selectedSnapshot.id}</p>
              </div>

              {selectedSnapshot.spec_url && (
                <div className="flex-shrink-0 p-3 rounded-lg bg-muted/50">
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

              <div className="flex flex-col min-h-0 flex-1 overflow-hidden">
                <p className="text-sm font-medium mb-2 flex-shrink-0">Schema Data</p>
                <div className="rounded-lg border bg-slate-950 overflow-auto p-4 flex-1 min-h-0">
                  <pre className="text-xs text-slate-100 font-mono whitespace-pre">
                    {JSON.stringify(selectedSnapshot.schema_data, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
