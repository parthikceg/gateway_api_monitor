import { useEffect, useState, useRef, useCallback } from 'react'
import { Filter, Sparkles, Code } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, type Change } from '@/lib/api'
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

interface ChangesProps {
  initialSeverity?: string
  initialTier?: string
  initialEndpoint?: string
  onNavigate?: (page: string, params?: Record<string, string>) => void
}

export function Changes({ initialSeverity, initialTier, initialEndpoint, onNavigate }: ChangesProps) {
  const [changes, setChanges] = useState<Change[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [availableEndpoints, setAvailableEndpoints] = useState<string[]>([])
  const [filters, setFilters] = useState({
    severity: initialSeverity || '',
    maturity: initialTier ? ({ stable: 'stable_change', preview: 'preview_change', beta: 'beta_change' }[initialTier] || '') : '',
    endpoint: initialEndpoint || '',
    schema_type: '',
    date_from: '',
    date_to: '',
  })
  const [offset, setOffset] = useState(0)
  const limit = 20

  useEffect(() => {
    loadEndpoints()
  }, [])

  useEffect(() => {
    if (initialSeverity) {
      setFilters(f => ({ ...f, severity: initialSeverity }))
    }
    if (initialTier) {
      setFilters(f => ({ ...f, tier: initialTier }))
    }
    if (initialEndpoint) {
      setFilters(f => ({ ...f, endpoint: initialEndpoint }))
    }
  }, [initialSeverity, initialTier, initialEndpoint])

  useEffect(() => {
    // Reset and reload when filters change
    setChanges([])
    setOffset(0)
    setHasMore(true)
    loadChanges(0)
  }, [filters])

  async function loadEndpoints() {
    try {
      const res = await api.getEndpoints()
      setAvailableEndpoints(res.endpoints)
    } catch (error) {
      console.error('Failed to load endpoints:', error)
    }
  }

  async function loadChanges(currentOffset: number) {
    const isInitialLoad = currentOffset === 0

    if (isInitialLoad) {
      setLoading(true)
    } else {
      setLoadingMore(true)
    }

    try {
      const params: { limit: number; offset: number; severity?: string; maturity?: string; endpoint?: string; schema_type?: string; date_from?: string; date_to?: string } = {
        limit,
        offset: currentOffset
      }
      if (filters.severity) params.severity = filters.severity
      if (filters.maturity) params.maturity = filters.maturity
      if (filters.endpoint) params.endpoint = filters.endpoint
      if (filters.schema_type) params.schema_type = filters.schema_type
      if (filters.date_from) params.date_from = new Date(filters.date_from).toISOString()
      if (filters.date_to) params.date_to = new Date(filters.date_to).toISOString()

      const res = await api.getChanges(params)

      if (isInitialLoad) {
        setChanges(res.changes)
      } else {
        setChanges(prev => [...prev, ...res.changes])
      }

      setHasMore(res.has_more)
      setOffset(currentOffset + res.changes.length)
    } catch (error) {
      console.error('Failed to load changes:', error)
    } finally {
      if (isInitialLoad) {
        setLoading(false)
      } else {
        setLoadingMore(false)
      }
    }
  }

  function loadMore() {
    if (!loadingMore && hasMore) {
      loadChanges(offset)
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

  const getChangeIcon = (type: string) => {
    switch (type) {
      case 'property_added': return '+'
      case 'property_removed': return '-'
      case 'type_changed': return '~'
      default: return '*'
    }
  }

  const recentChanges = changes.filter(c => {
    const daysSince = Math.floor((Date.now() - new Date(c.detected_at).getTime()) / (1000 * 60 * 60 * 24))
    return daysSince <= 90
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">API Changes</h2>
        <p className="text-muted-foreground">Track and filter changes across all tiers</p>
      </div>

      <Tabs defaultValue="recent">
        <TabsList className="bg-muted/50">
          <TabsTrigger value="recent" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
            Recent (90 days)
          </TabsTrigger>
          <TabsTrigger value="all" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
            All Changes
          </TabsTrigger>
        </TabsList>

        <div className="flex gap-4 mt-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Filters:</span>
          </div>
          
          <Select value={filters.severity || "all"} onValueChange={(value) => setFilters(f => ({ ...f, severity: value === "all" ? "" : value }))}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severities</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="info">Info</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filters.maturity || "all"} onValueChange={(value) => setFilters(f => ({ ...f, maturity: value === "all" ? "" : value }))}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Change Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="stable_change">Stable vs Previous</SelectItem>
              <SelectItem value="preview_change">Preview vs Previous</SelectItem>
              <SelectItem value="beta_change">Beta vs Previous</SelectItem>
              <SelectItem value="cross_tier_preview">Stable ↔ Preview</SelectItem>
              <SelectItem value="cross_tier_beta">Stable ↔ Beta</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filters.endpoint || "all"} onValueChange={(value) => setFilters(f => ({ ...f, endpoint: value === "all" ? "" : value }))}>
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

          <Select value={filters.schema_type || "all"} onValueChange={(value) => setFilters(f => ({ ...f, schema_type: value === "all" ? "" : value }))}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Schema" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Schemas</SelectItem>
              <SelectItem value="object">Object</SelectItem>
              <SelectItem value="request">Request</SelectItem>
            </SelectContent>
          </Select>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">From:</span>
            <input
              type="datetime-local"
              value={filters.date_from}
              onChange={(e) => setFilters(f => ({ ...f, date_from: e.target.value }))}
              className="h-9 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">To:</span>
            <input
              type="datetime-local"
              value={filters.date_to}
              onChange={(e) => setFilters(f => ({ ...f, date_to: e.target.value }))}
              className="h-9 rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm"
            />
          </div>

          {(filters.severity || filters.maturity || filters.endpoint || filters.schema_type || filters.date_from || filters.date_to) && (
            <Button variant="ghost" size="sm" onClick={() => setFilters({ severity: '', maturity: '', endpoint: '', schema_type: '', date_from: '', date_to: '' })}>
              Clear filters
            </Button>
          )}
        </div>

        <TabsContent value="recent">
          <ChangesList
            changes={recentChanges}
            loading={loading}
            loadingMore={loadingMore}
            hasMore={hasMore}
            onLoadMore={loadMore}
            getSeverityVariant={getSeverityVariant}
            getChangeIcon={getChangeIcon}
            onNavigate={onNavigate}
          />
        </TabsContent>

        <TabsContent value="all">
          <ChangesList
            changes={changes}
            loading={loading}
            loadingMore={loadingMore}
            hasMore={hasMore}
            onLoadMore={loadMore}
            getSeverityVariant={getSeverityVariant}
            getChangeIcon={getChangeIcon}
            onNavigate={onNavigate}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface ChangesListProps {
  changes: Change[]
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  onLoadMore: () => void
  getSeverityVariant: (severity: string) => string
  getChangeIcon: (type: string) => string
  onNavigate?: (page: string, params?: Record<string, string>) => void
}

function ChangesList({ changes, loading, loadingMore, hasMore, onLoadMore, getSeverityVariant, getChangeIcon, onNavigate }: ChangesListProps) {
  const observerTarget = useRef<HTMLDivElement>(null)

  const handleObserver = useCallback((entries: IntersectionObserverEntry[]) => {
    const [target] = entries
    if (target.isIntersecting && hasMore && !loadingMore) {
      onLoadMore()
    }
  }, [hasMore, loadingMore, onLoadMore])

  useEffect(() => {
    const element = observerTarget.current
    if (!element) return

    const observer = new IntersectionObserver(handleObserver, {
      root: null,
      rootMargin: '100px',
      threshold: 0.1
    })

    observer.observe(element)

    return () => {
      if (element) {
        observer.unobserve(element)
      }
    }
  }, [handleObserver])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  if (changes.length === 0) {
    return (
      <Card className="card-hover">
        <CardContent className="flex flex-col items-center justify-center h-64">
          <Sparkles className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium">No changes found</p>
          <p className="text-sm text-muted-foreground">Try adjusting your filters or run monitoring to detect changes</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {changes.map((change) => (
        <Card key={change.id} className="card-hover">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-primary/10 to-purple-500/10 font-mono text-sm font-bold text-primary">
                  {getChangeIcon(change.type)}
                </span>
                <div>
                  <CardTitle className="text-base">{change.field}</CardTitle>
                  <CardDescription className="capitalize">{change.type.replace(/_/g, ' ')}</CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={getSeverityVariant(change.severity) as 'high' | 'medium' | 'low' | 'info'} className="capitalize">
                  {change.severity}
                </Badge>
                <span className={`badge-${change.tier} px-2.5 py-1 rounded-full text-xs font-semibold`}>
                  {change.maturity ? ({
                    stable_change: 'Stable',
                    preview_change: 'Preview',
                    beta_change: 'Beta',
                    cross_tier_preview: 'Stable ↔ Preview',
                    cross_tier_beta: 'Stable ↔ Beta',
                  }[change.maturity] || change.tier) : change.tier}
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {change.endpoint && (
              <div className="mb-2">
                <button
                  onClick={() => onNavigate?.('explorer', { endpoint: change.endpoint! })}
                  className="inline-flex items-center gap-1.5 text-xs bg-slate-100 hover:bg-slate-200 px-2 py-1 rounded-md transition-colors"
                >
                  <Code className="h-3 w-3 text-primary" />
                  <span className="font-medium">{formatEndpointName(change.endpoint)}</span>
                  <span className="text-muted-foreground font-mono">{change.endpoint}</span>
                </button>
              </div>
            )}
            {change.summary && (
              <p className="text-sm text-muted-foreground mb-2">{change.summary}</p>
            )}
            {(change.old_value || change.new_value) && (
              <div className="mb-3 p-2 bg-slate-50 rounded-md border border-slate-200">
                <div className="text-xs font-medium text-slate-500 mb-1">Value Change:</div>
                <div className="flex items-center gap-2 font-mono text-sm">
                  <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded line-through">
                    {change.old_value || '(empty)'}
                  </span>
                  <span className="text-slate-400">→</span>
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded">
                    {change.new_value || '(empty)'}
                  </span>
                </div>
              </div>
            )}
            <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
              <span>Detected: {formatDate(change.detected_at)}</span>
              <span>{formatRelativeTime(change.detected_at)}</span>
              {change.category && <Badge variant="outline" className="text-xs">{change.category}</Badge>}
            </div>
          </CardContent>
        </Card>
      ))}

      {/* Infinite scroll observer target */}
      <div ref={observerTarget} className="h-4" />

      {/* Loading indicator */}
      {loadingMore && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
          <span className="ml-3 text-sm text-muted-foreground">Loading more changes...</span>
        </div>
      )}

      {/* End of list indicator */}
      {!hasMore && changes.length > 0 && (
        <div className="flex items-center justify-center py-8">
          <span className="text-sm text-muted-foreground">No more changes to load</span>
        </div>
      )}
    </div>
  )
}
