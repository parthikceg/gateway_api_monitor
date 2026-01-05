import { useEffect, useState } from 'react'
import { Filter, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api, type Change } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'

interface ChangesProps {
  initialSeverity?: string
  initialTier?: string
}

export function Changes({ initialSeverity, initialTier }: ChangesProps) {
  const [changes, setChanges] = useState<Change[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    severity: initialSeverity || '',
    tier: initialTier || '',
    limit: 50,
  })

  useEffect(() => {
    if (initialSeverity) {
      setFilters(f => ({ ...f, severity: initialSeverity }))
    }
    if (initialTier) {
      setFilters(f => ({ ...f, tier: initialTier }))
    }
  }, [initialSeverity, initialTier])

  useEffect(() => {
    loadChanges()
  }, [filters])

  async function loadChanges() {
    setLoading(true)
    try {
      const params: { limit: number; severity?: string; tier?: string } = { limit: filters.limit }
      if (filters.severity) params.severity = filters.severity
      if (filters.tier) params.tier = filters.tier
      
      const res = await api.getChanges(params)
      setChanges(res.changes)
    } catch (error) {
      console.error('Failed to load changes:', error)
    } finally {
      setLoading(false)
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

          <Select value={filters.tier || "all"} onValueChange={(value) => setFilters(f => ({ ...f, tier: value === "all" ? "" : value }))}>
            <SelectTrigger className="w-[130px]">
              <SelectValue placeholder="Tier" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tiers</SelectItem>
              <SelectItem value="stable">Stable</SelectItem>
              <SelectItem value="preview">Preview</SelectItem>
              <SelectItem value="beta">Beta</SelectItem>
            </SelectContent>
          </Select>

          {(filters.severity || filters.tier) && (
            <Button variant="ghost" size="sm" onClick={() => setFilters({ severity: '', tier: '', limit: 50 })}>
              Clear filters
            </Button>
          )}
        </div>

        <TabsContent value="recent">
          <ChangesList changes={recentChanges} loading={loading} getSeverityVariant={getSeverityVariant} getChangeIcon={getChangeIcon} />
        </TabsContent>
        
        <TabsContent value="all">
          <ChangesList changes={changes} loading={loading} getSeverityVariant={getSeverityVariant} getChangeIcon={getChangeIcon} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface ChangesListProps {
  changes: Change[]
  loading: boolean
  getSeverityVariant: (severity: string) => string
  getChangeIcon: (type: string) => string
}

function ChangesList({ changes, loading, getSeverityVariant, getChangeIcon }: ChangesListProps) {
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
              <div className="flex items-center gap-2">
                <Badge variant={getSeverityVariant(change.severity) as 'high' | 'medium' | 'low' | 'info'} className="capitalize">
                  {change.severity}
                </Badge>
                <span className={`badge-${change.tier} px-2.5 py-1 rounded-full text-xs font-semibold capitalize`}>
                  {change.tier}
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            {change.summary && (
              <p className="text-sm text-muted-foreground mb-2">{change.summary}</p>
            )}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>Detected: {formatDate(change.detected_at)}</span>
              <span>{formatRelativeTime(change.detected_at)}</span>
              {change.category && <Badge variant="outline" className="text-xs">{change.category}</Badge>}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
