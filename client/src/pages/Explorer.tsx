import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, MessageSquare, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ChatWidget } from '@/components/ChatWidget'
import { api, type Snapshot } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Field {
  name: string
  type: string
  description?: string
  required?: boolean
  deprecated?: boolean
  children?: Field[]
  availability?: 'stable' | 'preview' | 'beta' | 'all'
}

interface ExplorerProps {
  initialTier?: string
}

export function Explorer({ initialTier }: ExplorerProps) {
  const [snapshots, setSnapshots] = useState<{ stable?: Snapshot; preview?: Snapshot; beta?: Snapshot }>({})
  const [loading, setLoading] = useState(true)
  const [activeTier, setActiveTier] = useState(initialTier || 'stable')
  const [chatField, setChatField] = useState<{
    name: string
    type: string
    description?: string
    tier?: string
  } | null>(null)
  const [fieldAvailability, setFieldAvailability] = useState<{
    beta_only: string[]
    preview_only: string[]
  }>({ beta_only: [], preview_only: [] })

  useEffect(() => {
    if (initialTier) {
      setActiveTier(initialTier)
    }
  }, [initialTier])

  useEffect(() => {
    loadSnapshots()
  }, [])

  async function loadSnapshots() {
    try {
      const [stableRes, previewRes, betaRes] = await Promise.all([
        api.getSnapshots({ limit: 1, tier: 'stable' }),
        api.getSnapshots({ limit: 1, tier: 'preview' }),
        api.getSnapshots({ limit: 1, tier: 'beta' }),
      ])

      const snapshots: { stable?: Snapshot; preview?: Snapshot; beta?: Snapshot } = {}
      
      if (stableRes.snapshots[0]) {
        snapshots.stable = await api.getSnapshotDetail(stableRes.snapshots[0].id)
      }
      if (previewRes.snapshots[0]) {
        snapshots.preview = await api.getSnapshotDetail(previewRes.snapshots[0].id)
      }
      if (betaRes.snapshots[0]) {
        snapshots.beta = await api.getSnapshotDetail(betaRes.snapshots[0].id)
      }

      setSnapshots(snapshots)

      const stableFields = new Set(parseSchemaFieldNames(snapshots.stable?.schema_data))
      const previewFields = new Set(parseSchemaFieldNames(snapshots.preview?.schema_data))
      const betaFields = new Set(parseSchemaFieldNames(snapshots.beta?.schema_data))

      const betaOnly = [...betaFields].filter(f => !stableFields.has(f) && !previewFields.has(f))
      const previewOnly = [...previewFields].filter(f => !stableFields.has(f))

      setFieldAvailability({ beta_only: betaOnly, preview_only: previewOnly })
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    } finally {
      setLoading(false)
    }
  }

  function parseSchemaFieldNames(schema: Record<string, unknown> | undefined): string[] {
    if (!schema) return []
    const properties = (schema.properties || schema) as Record<string, unknown>
    return Object.keys(properties)
  }

  function parseSchemaToFields(schema: Record<string, unknown> | undefined): Field[] {
    if (!schema) return []
    
    const properties = (schema.properties || schema) as Record<string, unknown>
    const required = (schema.required || []) as string[]
    
    return Object.entries(properties).map(([name, value]) => {
      const fieldDef = value as Record<string, unknown>
      let availability: Field['availability'] = 'all'
      
      if (fieldAvailability.beta_only.includes(name)) {
        availability = 'beta'
      } else if (fieldAvailability.preview_only.includes(name)) {
        availability = 'preview'
      }

      return {
        name,
        type: (fieldDef.type as string) || 'object',
        description: fieldDef.description as string | undefined,
        required: required.includes(name),
        deprecated: fieldDef.deprecated as boolean | undefined,
        children: fieldDef.properties ? parseSchemaToFields(fieldDef as Record<string, unknown>) : undefined,
        availability,
      }
    })
  }

  const stableFields = parseSchemaToFields(snapshots.stable?.schema_data)
  const previewFields = parseSchemaToFields(snapshots.preview?.schema_data)
  const betaFields = parseSchemaToFields(snapshots.beta?.schema_data)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Object Explorer</h2>
        <p className="text-muted-foreground">Explore the full structure of monitored API objects</p>
      </div>

      <div className="flex gap-4 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-3 h-3 rounded field-beta-only" />
          <span className="text-muted-foreground">Beta Only</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-3 h-3 rounded field-preview-only" />
          <span className="text-muted-foreground">Preview Only</span>
        </div>
      </div>

      <Tabs value={activeTier} onValueChange={setActiveTier}>
        <TabsList className="bg-muted/50">
          <TabsTrigger value="stable" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
            <span className="badge-stable px-2 py-0.5 rounded-full text-xs font-semibold mr-2">GA</span>
            Stable ({stableFields.length} fields)
          </TabsTrigger>
          <TabsTrigger value="preview" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
            <span className="badge-preview px-2 py-0.5 rounded-full text-xs font-semibold mr-2">Preview</span>
            Preview ({previewFields.length} fields)
          </TabsTrigger>
          <TabsTrigger value="beta" className="data-[state=active]:bg-white data-[state=active]:shadow-sm">
            <span className="badge-beta px-2 py-0.5 rounded-full text-xs font-semibold mr-2">Beta</span>
            Beta ({betaFields.length} fields)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stable">
          <FieldExplorer 
            fields={stableFields} 
            tier="stable"
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'stable' })}
          />
        </TabsContent>
        
        <TabsContent value="preview">
          <FieldExplorer 
            fields={previewFields} 
            tier="preview"
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'preview' })}
          />
        </TabsContent>
        
        <TabsContent value="beta">
          <FieldExplorer 
            fields={betaFields} 
            tier="beta"
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'beta' })}
          />
        </TabsContent>
      </Tabs>

      <ChatWidget 
        fieldContext={chatField} 
        onClose={() => setChatField(null)}
      />
    </div>
  )
}

interface FieldExplorerProps {
  fields: Field[]
  tier: string
  fieldAvailability: { beta_only: string[]; preview_only: string[] }
  onAskAI: (field: { name: string; type: string; description?: string }) => void
}

function FieldExplorer({ fields, tier, fieldAvailability, onAskAI }: FieldExplorerProps) {
  if (fields.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center h-64">
          <p className="text-lg font-medium">No fields available</p>
          <p className="text-sm text-muted-foreground">Run monitoring to capture API snapshots</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle>Payment Intents</CardTitle>
        <CardDescription>Stripe API object structure for {tier} tier</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px]">
          <div className="space-y-1">
            {fields.map((field) => (
              <FieldRow 
                key={field.name} 
                field={field} 
                depth={0} 
                fieldAvailability={fieldAvailability}
                onAskAI={onAskAI} 
              />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

interface FieldRowProps {
  field: Field
  depth: number
  fieldAvailability: { beta_only: string[]; preview_only: string[] }
  onAskAI: (field: { name: string; type: string; description?: string }) => void
}

function FieldRow({ field, depth, fieldAvailability, onAskAI }: FieldRowProps) {
  const [expanded, setExpanded] = useState(false)
  const hasChildren = field.children && field.children.length > 0
  
  const isBetaOnly = fieldAvailability.beta_only.includes(field.name)
  const isPreviewOnly = fieldAvailability.preview_only.includes(field.name)

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-2 p-2.5 rounded-lg cursor-pointer group transition-all",
          isBetaOnly && "field-beta-only",
          isPreviewOnly && "field-preview-only",
          !isBetaOnly && !isPreviewOnly && "hover:bg-muted/50"
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />
        ) : (
          <div className="w-4" />
        )}
        
        <span className="font-mono text-sm font-medium">{field.name}</span>
        
        <Badge variant="outline" className="text-xs bg-background">
          {field.type}
        </Badge>
        
        {field.required && (
          <Badge variant="destructive" className="text-xs">required</Badge>
        )}
        
        {field.deprecated && (
          <Badge variant="secondary" className="text-xs line-through">deprecated</Badge>
        )}

        {isBetaOnly && (
          <span className="badge-beta px-1.5 py-0.5 rounded text-xs font-medium">Beta Only</span>
        )}

        {isPreviewOnly && (
          <span className="badge-preview px-1.5 py-0.5 rounded text-xs font-medium">Preview Only</span>
        )}

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          className="opacity-0 group-hover:opacity-100 transition-opacity gap-1.5 text-primary hover:text-primary"
          onClick={(e) => {
            e.stopPropagation()
            onAskAI({ name: field.name, type: field.type, description: field.description })
          }}
        >
          <Sparkles className="h-3 w-3" />
          Ask AI
        </Button>
      </div>

      {field.description && (
        <p 
          className="text-xs text-muted-foreground pl-6 pb-1"
          style={{ paddingLeft: `${depth * 20 + 32}px` }}
        >
          {field.description}
        </p>
      )}

      {expanded && hasChildren && (
        <div>
          {field.children!.map((child) => (
            <FieldRow 
              key={child.name} 
              field={child} 
              depth={depth + 1} 
              fieldAvailability={fieldAvailability}
              onAskAI={onAskAI} 
            />
          ))}
        </div>
      )}
    </div>
  )
}
