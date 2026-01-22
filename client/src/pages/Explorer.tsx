import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, MessageSquare, Sparkles, Code } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ChatWidget } from '@/components/ChatWidget'
import { api, type Snapshot } from '@/lib/api'
import { cn } from '@/lib/utils'

// Helper to format endpoint path to display name
function formatEndpointName(endpoint: string): string {
  if (!endpoint) return 'Unknown'
  return endpoint
    .replace('/v1/', '')
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

interface Field {
  name: string
  type: string
  description?: string
  required?: boolean
  deprecated?: boolean
  children?: Field[]
  availability?: 'stable' | 'preview' | 'beta' | 'all'
  enumValues?: string[]
  newEnumValues?: string[]
}

interface ExplorerProps {
  initialTier?: string
  initialEndpoint?: string
}

export function Explorer({ initialTier, initialEndpoint }: ExplorerProps) {
  const [snapshots, setSnapshots] = useState<{ stable?: Snapshot; preview?: Snapshot; beta?: Snapshot }>({})
  const [loading, setLoading] = useState(true)
  const [activeTier, setActiveTier] = useState(initialTier || 'stable')
  const [availableEndpoints, setAvailableEndpoints] = useState<string[]>([])
  const [selectedEndpoint, setSelectedEndpoint] = useState<string>(initialEndpoint || '/v1/payment_intents')
  const [chatField, setChatField] = useState<{
    name: string
    type: string
    description?: string
    tier?: string
    endpoint?: string
  } | null>(null)
  const [fieldAvailability, setFieldAvailability] = useState<{
    beta_only: string[]
    preview_only: string[]
    enum_diff: Record<string, { beta_new: string[]; preview_new: string[] }>
  }>({ beta_only: [], preview_only: [], enum_diff: {} })

  useEffect(() => {
    if (initialTier) {
      setActiveTier(initialTier)
    }
  }, [initialTier])

  useEffect(() => {
    if (initialEndpoint) {
      setSelectedEndpoint(initialEndpoint)
    }
  }, [initialEndpoint])

  useEffect(() => {
    loadEndpoints()
  }, [])

  useEffect(() => {
    if (selectedEndpoint) {
      loadSnapshots()
    }
  }, [selectedEndpoint])

  async function loadEndpoints() {
    try {
      const res = await api.getEndpoints()
      setAvailableEndpoints(res.endpoints)
      if (res.endpoints.length > 0 && !initialEndpoint) {
        setSelectedEndpoint(res.endpoints[0])
      }
    } catch (error) {
      console.error('Failed to load endpoints:', error)
    }
  }

  async function loadSnapshots() {
    setLoading(true)
    try {
      // Get latest snapshot for selected endpoint in each tier
      const [stableRes, previewRes, betaRes] = await Promise.all([
        api.getSnapshots({ limit: 50, tier: 'stable' }),
        api.getSnapshots({ limit: 50, tier: 'preview' }),
        api.getSnapshots({ limit: 50, tier: 'beta' }),
      ])

      // Filter to find the snapshot for the selected endpoint
      const findEndpointSnapshot = (snapshots: Snapshot[]) =>
        snapshots.find(s => s.endpoint === selectedEndpoint)

      const snapshots: { stable?: Snapshot; preview?: Snapshot; beta?: Snapshot } = {}

      const stableSnapshot = findEndpointSnapshot(stableRes.snapshots)
      const previewSnapshot = findEndpointSnapshot(previewRes.snapshots)
      const betaSnapshot = findEndpointSnapshot(betaRes.snapshots)

      if (stableSnapshot) {
        snapshots.stable = await api.getSnapshotDetail(stableSnapshot.id)
      }
      if (previewSnapshot) {
        snapshots.preview = await api.getSnapshotDetail(previewSnapshot.id)
      }
      if (betaSnapshot) {
        snapshots.beta = await api.getSnapshotDetail(betaSnapshot.id)
      }

      setSnapshots(snapshots)

      const stableFields = new Set(parseSchemaFieldNames(snapshots.stable?.schema_data))
      const previewFields = new Set(parseSchemaFieldNames(snapshots.preview?.schema_data))
      const betaFields = new Set(parseSchemaFieldNames(snapshots.beta?.schema_data))

      const betaOnly = [...betaFields].filter(f => !stableFields.has(f) && !previewFields.has(f))
      const previewOnly = [...previewFields].filter(f => !stableFields.has(f))

      const stableEnums = parseSchemaEnumValues(snapshots.stable?.schema_data)
      const previewEnums = parseSchemaEnumValues(snapshots.preview?.schema_data)
      const betaEnums = parseSchemaEnumValues(snapshots.beta?.schema_data)
      
      const enumDiff: Record<string, { beta_new: string[]; preview_new: string[] }> = {}
      
      const allFieldNames = new Set([...Object.keys(stableEnums), ...Object.keys(previewEnums), ...Object.keys(betaEnums)])
      allFieldNames.forEach(fieldName => {
        const stableVals = new Set(stableEnums[fieldName] || [])
        const previewVals = previewEnums[fieldName] || []
        const betaVals = betaEnums[fieldName] || []
        
        const previewNew = previewVals.filter(v => !stableVals.has(v))
        const betaNew = betaVals.filter(v => !stableVals.has(v))
        
        if (previewNew.length > 0 || betaNew.length > 0) {
          enumDiff[fieldName] = { beta_new: betaNew, preview_new: previewNew }
        }
      })

      setFieldAvailability({ beta_only: betaOnly, preview_only: previewOnly, enum_diff: enumDiff })
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    } finally {
      setLoading(false)
    }
  }

  function resolveSchemaObject(fieldDef: Record<string, unknown>): Record<string, unknown> | undefined {
    if (fieldDef.properties) {
      return fieldDef
    }
    const compositionKeys = ['anyOf', 'oneOf', 'allOf'] as const
    for (const key of compositionKeys) {
      const arr = fieldDef[key]
      if (Array.isArray(arr)) {
        for (const variant of arr) {
          if (typeof variant === 'object' && variant !== null) {
            const resolved = resolveSchemaObject(variant as Record<string, unknown>)
            if (resolved) return resolved
          }
        }
      }
    }
    if (fieldDef.items && typeof fieldDef.items === 'object') {
      return resolveSchemaObject(fieldDef.items as Record<string, unknown>)
    }
    return undefined
  }

  function parseSchemaFieldNames(schema: Record<string, unknown> | undefined, prefix: string = ''): string[] {
    if (!schema) return []
    const resolved = resolveSchemaObject(schema) || schema
    const properties = (resolved.properties || resolved) as Record<string, unknown>
    const result: string[] = []
    
    Object.entries(properties).forEach(([name, value]) => {
      const fieldPath = prefix ? `${prefix}.${name}` : name
      result.push(fieldPath)
      
      const fieldDef = value as Record<string, unknown>
      const nestedSchema = resolveSchemaObject(fieldDef)
      if (nestedSchema) {
        result.push(...parseSchemaFieldNames(nestedSchema, fieldPath))
      }
    })
    
    return result
  }

  function parseSchemaEnumValues(schema: Record<string, unknown> | undefined, prefix: string = ''): Record<string, string[]> {
    if (!schema) return {}
    const resolved = resolveSchemaObject(schema) || schema
    const properties = (resolved.properties || resolved) as Record<string, unknown>
    const result: Record<string, string[]> = {}
    
    Object.entries(properties).forEach(([name, value]) => {
      const fieldDef = value as Record<string, unknown>
      const fieldPath = prefix ? `${prefix}.${name}` : name
      
      if (fieldDef.enum && Array.isArray(fieldDef.enum)) {
        result[fieldPath] = fieldDef.enum as string[]
      }
      if (fieldDef.items && typeof fieldDef.items === 'object') {
        const items = fieldDef.items as Record<string, unknown>
        if (items.enum && Array.isArray(items.enum)) {
          result[fieldPath] = items.enum as string[]
        }
      }
      const nestedSchema = resolveSchemaObject(fieldDef)
      if (nestedSchema) {
        Object.assign(result, parseSchemaEnumValues(nestedSchema, fieldPath))
      }
    })
    
    return result
  }

  function parseSchemaToFields(schema: Record<string, unknown> | undefined, tier: string = 'stable', prefix: string = ''): Field[] {
    if (!schema) return []
    
    const resolved = resolveSchemaObject(schema) || schema
    const properties = (resolved.properties || resolved) as Record<string, unknown>
    const required = (resolved.required || []) as string[]
    
    return Object.entries(properties).map(([name, value]) => {
      const fieldDef = value as Record<string, unknown>
      const fieldPath = prefix ? `${prefix}.${name}` : name
      let availability: Field['availability'] = 'all'
      
      if (fieldAvailability.beta_only.includes(fieldPath)) {
        availability = 'beta'
      } else if (fieldAvailability.preview_only.includes(fieldPath)) {
        availability = 'preview'
      }

      let enumValues: string[] | undefined
      if (fieldDef.enum && Array.isArray(fieldDef.enum)) {
        enumValues = fieldDef.enum as string[]
      } else if (fieldDef.items && typeof fieldDef.items === 'object') {
        const items = fieldDef.items as Record<string, unknown>
        if (items.enum && Array.isArray(items.enum)) {
          enumValues = items.enum as string[]
        }
      }

      let newEnumValues: string[] | undefined
      const diff = fieldAvailability.enum_diff[fieldPath]
      if (diff) {
        if (tier === 'beta' && diff.beta_new.length > 0) {
          newEnumValues = diff.beta_new
        } else if (tier === 'preview' && diff.preview_new.length > 0) {
          newEnumValues = diff.preview_new
        }
      }

      let children: Field[] | undefined
      const nestedSchema = resolveSchemaObject(fieldDef)
      if (nestedSchema) {
        children = parseSchemaToFields(nestedSchema, tier, fieldPath)
      }

      return {
        name,
        type: (fieldDef.type as string) || 'object',
        description: fieldDef.description as string | undefined,
        required: required.includes(name),
        deprecated: fieldDef.deprecated as boolean | undefined,
        children,
        availability,
        enumValues,
        newEnumValues,
      }
    })
  }

  const stableFields = parseSchemaToFields(snapshots.stable?.schema_data, 'stable')
  const previewFields = parseSchemaToFields(snapshots.preview?.schema_data, 'preview')
  const betaFields = parseSchemaToFields(snapshots.beta?.schema_data, 'beta')

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold">Object Explorer</h2>
          <p className="text-muted-foreground">Explore the full structure of monitored API objects</p>
        </div>
        <div className="flex items-center gap-3">
          <Code className="h-5 w-5 text-primary" />
          <Select value={selectedEndpoint} onValueChange={setSelectedEndpoint}>
            <SelectTrigger className="w-[240px]">
              <SelectValue placeholder="Select endpoint" />
            </SelectTrigger>
            <SelectContent>
              {availableEndpoints.map((endpoint) => (
                <SelectItem key={endpoint} value={endpoint}>
                  <div className="flex flex-col">
                    <span className="font-medium">{formatEndpointName(endpoint)}</span>
                    <span className="text-xs text-muted-foreground font-mono">{endpoint}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
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
        <div className="flex items-center gap-2 text-sm">
          <div className="w-3 h-3 rounded bg-gradient-to-r from-amber-100 to-orange-100 border border-orange-200" />
          <span className="text-muted-foreground">Has New Values</span>
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
            endpoint={selectedEndpoint}
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'stable', endpoint: selectedEndpoint })}
          />
        </TabsContent>

        <TabsContent value="preview">
          <FieldExplorer
            fields={previewFields}
            tier="preview"
            endpoint={selectedEndpoint}
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'preview', endpoint: selectedEndpoint })}
          />
        </TabsContent>

        <TabsContent value="beta">
          <FieldExplorer
            fields={betaFields}
            tier="beta"
            endpoint={selectedEndpoint}
            fieldAvailability={fieldAvailability}
            onAskAI={(field) => setChatField({ ...field, tier: 'beta', endpoint: selectedEndpoint })}
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
  endpoint: string
  fieldAvailability: { beta_only: string[]; preview_only: string[] }
  onAskAI: (field: { name: string; type: string; description?: string }) => void
}

function FieldExplorer({ fields, tier, endpoint, fieldAvailability, onAskAI }: FieldExplorerProps) {
  if (fields.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center h-64">
          <p className="text-lg font-medium">No fields available</p>
          <p className="text-sm text-muted-foreground">Run monitoring to capture API snapshots for this endpoint</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Code className="h-5 w-5 text-primary" />
          {formatEndpointName(endpoint)}
        </CardTitle>
        <CardDescription>
          <span className="font-mono text-xs">{endpoint}</span>
          <span className="mx-2">•</span>
          Stripe API object structure for {tier} tier
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px]">
          <div className="space-y-1">
            {fields.map((field) => (
              <FieldRow 
                key={field.name} 
                field={field} 
                depth={0}
                fieldPath={field.name}
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
  fieldPath: string
  fieldAvailability: { beta_only: string[]; preview_only: string[] }
  onAskAI: (field: { name: string; type: string; description?: string }) => void
}

function FieldRow({ field, depth, fieldPath, fieldAvailability, onAskAI }: FieldRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [showAllEnums, setShowAllEnums] = useState(false)
  const hasChildren = field.children && field.children.length > 0
  
  const isBetaOnly = fieldAvailability.beta_only.includes(fieldPath)
  const isPreviewOnly = fieldAvailability.preview_only.includes(fieldPath)
  const hasEnumValues = field.enumValues && field.enumValues.length > 0
  const newValuesSet = new Set(field.newEnumValues || [])

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

        {field.newEnumValues && field.newEnumValues.length > 0 && (
          <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gradient-to-r from-amber-100 to-orange-100 text-orange-700 border border-orange-200">
            {field.newEnumValues.length} new value{field.newEnumValues.length > 1 ? 's' : ''}
          </span>
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

      {hasEnumValues && (
        <div 
          className="text-xs pb-2"
          style={{ paddingLeft: `${depth * 20 + 32}px` }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-muted-foreground">
              Possible values ({field.enumValues!.length}):
            </span>
            {field.enumValues!.length > 10 && (
              <button
                onClick={() => setShowAllEnums(!showAllEnums)}
                className="text-primary hover:underline text-xs"
              >
                {showAllEnums ? 'Show less' : 'Show all'}
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {(showAllEnums ? field.enumValues! : field.enumValues!.slice(0, 10)).map((val) => (
              <span 
                key={val} 
                className={cn(
                  "inline-flex px-2 py-0.5 rounded font-mono text-xs",
                  newValuesSet.has(val)
                    ? "bg-gradient-to-r from-amber-50 to-orange-50 text-orange-700 border border-orange-200"
                    : "bg-muted/50 text-muted-foreground border border-muted"
                )}
              >
                {val}
                {newValuesSet.has(val) && <span className="ml-1 text-orange-500">*</span>}
              </span>
            ))}
            {!showAllEnums && field.enumValues!.length > 10 && (
              <span className="text-muted-foreground px-2 py-0.5">
                +{field.enumValues!.length - 10} more
              </span>
            )}
          </div>
          {field.newEnumValues && field.newEnumValues.length > 0 && (
            <p className="text-orange-600 mt-1 text-xs">* New in this tier</p>
          )}
        </div>
      )}

      {expanded && hasChildren && (
        <div>
          {field.children!.map((child) => (
            <FieldRow 
              key={child.name} 
              field={child} 
              depth={depth + 1}
              fieldPath={fieldPath ? `${fieldPath}.${child.name}` : child.name}
              fieldAvailability={fieldAvailability}
              onAskAI={onAskAI} 
            />
          ))}
        </div>
      )}
    </div>
  )
}
