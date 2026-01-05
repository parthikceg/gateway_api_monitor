import { useState } from 'react'
import { ArrowRight, GitCompare, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api } from '@/lib/api'

interface ComparisonResult {
  source: string
  target: string
  changes: Array<{
    type: string
    field: string
    old_value?: unknown
    new_value?: unknown
  }>
  upcoming_features_count: number
}

export function Compare() {
  const [source, setSource] = useState('preview')
  const [target, setTarget] = useState('stable')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ComparisonResult | null>(null)

  async function handleCompare() {
    setLoading(true)
    try {
      const res = await api.compareTiers(source, target)
      setResult(res as ComparisonResult)
    } catch (error) {
      console.error('Failed to compare:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Snapshot Comparison</h2>
        <p className="text-muted-foreground">Compare API versions across different tiers</p>
      </div>

      <Card className="stat-card card-hover">
        <CardHeader>
          <CardTitle>Compare Tiers</CardTitle>
          <CardDescription>
            Select two tiers to compare and see upcoming features or changes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1 min-w-[150px]">
              <label className="text-sm font-medium mb-2 block">Source Tier</label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="beta">Beta</SelectItem>
                  <SelectItem value="preview">Preview</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <ArrowRight className="h-5 w-5 text-muted-foreground mt-6" />

            <div className="flex-1 min-w-[150px]">
              <label className="text-sm font-medium mb-2 block">Target Tier</label>
              <Select value={target} onValueChange={setTarget}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="stable">Stable</SelectItem>
                  <SelectItem value="preview">Preview</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button 
              onClick={handleCompare} 
              disabled={loading} 
              className="mt-6 bg-gradient-to-r from-primary to-purple-600 hover:from-primary/90 hover:to-purple-600/90"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Comparing...
                </>
              ) : (
                <>
                  <GitCompare className="h-4 w-4 mr-2" />
                  Compare
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card 
          className="card-hover cursor-pointer border-2 border-transparent hover:border-primary/20 transition-all" 
          onClick={() => { setSource('preview'); setTarget('stable'); handleCompare() }}
        >
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <span className="badge-preview px-2 py-0.5 rounded-full text-xs font-semibold">Preview</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="badge-stable px-2 py-0.5 rounded-full text-xs font-semibold">Stable</span>
            </CardTitle>
            <CardDescription>See what's coming to GA soon</CardDescription>
          </CardHeader>
        </Card>

        <Card 
          className="card-hover cursor-pointer border-2 border-transparent hover:border-primary/20 transition-all" 
          onClick={() => { setSource('beta'); setTarget('stable'); handleCompare() }}
        >
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <span className="badge-beta px-2 py-0.5 rounded-full text-xs font-semibold">Beta</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="badge-stable px-2 py-0.5 rounded-full text-xs font-semibold">Stable</span>
            </CardTitle>
            <CardDescription>Experimental features vs GA</CardDescription>
          </CardHeader>
        </Card>

        <Card 
          className="card-hover cursor-pointer border-2 border-transparent hover:border-primary/20 transition-all" 
          onClick={() => { setSource('beta'); setTarget('preview'); handleCompare() }}
        >
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <span className="badge-beta px-2 py-0.5 rounded-full text-xs font-semibold">Beta</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="badge-preview px-2 py-0.5 rounded-full text-xs font-semibold">Preview</span>
            </CardTitle>
            <CardDescription>What's graduating from beta</CardDescription>
          </CardHeader>
        </Card>
      </div>

      {result && (
        <Card className="card-hover">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Comparison Results
              <span className={`badge-${result.source} px-2 py-0.5 rounded-full text-xs font-semibold capitalize`}>
                {result.source}
              </span>
              <ArrowRight className="h-4 w-4" />
              <span className={`badge-${result.target} px-2 py-0.5 rounded-full text-xs font-semibold capitalize`}>
                {result.target}
              </span>
            </CardTitle>
            <CardDescription>
              {result.upcoming_features_count} upcoming features found
            </CardDescription>
          </CardHeader>
          <CardContent>
            {result.changes.length === 0 ? (
              <div className="text-center py-8">
                <GitCompare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-lg font-medium">No differences found</p>
                <p className="text-sm text-muted-foreground">These tiers are in sync</p>
              </div>
            ) : (
              <div className="space-y-3">
                {result.changes.map((change, idx) => (
                  <div key={idx} className="p-4 border rounded-xl bg-gradient-to-r from-transparent to-muted/30 hover:to-muted/50 transition-colors">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="capitalize bg-background">
                        {change.type.replace(/_/g, ' ')}
                      </Badge>
                      <span className="font-mono text-sm font-medium">{change.field}</span>
                    </div>
                    {(change.old_value !== undefined || change.new_value !== undefined) && (
                      <div className="flex gap-4 text-sm">
                        {change.old_value !== undefined && (
                          <div className="flex-1">
                            <span className="text-muted-foreground">Old: </span>
                            <code className="bg-red-50 text-red-700 px-2 py-0.5 rounded">
                              {JSON.stringify(change.old_value)}
                            </code>
                          </div>
                        )}
                        {change.new_value !== undefined && (
                          <div className="flex-1">
                            <span className="text-muted-foreground">New: </span>
                            <code className="bg-green-50 text-green-700 px-2 py-0.5 rounded">
                              {JSON.stringify(change.new_value)}
                            </code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
