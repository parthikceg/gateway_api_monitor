import { useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, MessageSquare, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type Snapshot } from '@/lib/api'

interface Field {
  name: string
  type: string
  description?: string
  required?: boolean
  deprecated?: boolean
  children?: Field[]
}

export function Explorer() {
  const [snapshots, setSnapshots] = useState<{ stable?: Snapshot; preview?: Snapshot; beta?: Snapshot }>({})
  const [loading, setLoading] = useState(true)
  const [selectedField, setSelectedField] = useState<Field | null>(null)
  const [aiDialogOpen, setAiDialogOpen] = useState(false)
  const [aiQuestion, setAiQuestion] = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [aiLoading, setAiLoading] = useState(false)

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
    } catch (error) {
      console.error('Failed to load snapshots:', error)
    } finally {
      setLoading(false)
    }
  }

  function parseSchemaToFields(schema: Record<string, unknown> | undefined): Field[] {
    if (!schema) return []
    
    const properties = (schema.properties || schema) as Record<string, unknown>
    const required = (schema.required || []) as string[]
    
    return Object.entries(properties).map(([name, value]) => {
      const fieldDef = value as Record<string, unknown>
      return {
        name,
        type: (fieldDef.type as string) || 'object',
        description: fieldDef.description as string | undefined,
        required: required.includes(name),
        deprecated: fieldDef.deprecated as boolean | undefined,
        children: fieldDef.properties ? parseSchemaToFields(fieldDef as Record<string, unknown>) : undefined,
      }
    })
  }

  async function handleAskAI() {
    if (!selectedField || !aiQuestion.trim()) return
    
    setAiLoading(true)
    try {
      const res = await api.askAI(aiQuestion, { field: selectedField })
      setAiAnswer(res.answer)
    } catch (error) {
      setAiAnswer('Sorry, I was unable to process your question. Please try again.')
    } finally {
      setAiLoading(false)
    }
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

      <Tabs defaultValue="stable">
        <TabsList>
          <TabsTrigger value="stable">
            <Badge variant="stable" className="mr-2">GA</Badge>
            Stable ({stableFields.length} fields)
          </TabsTrigger>
          <TabsTrigger value="preview">
            <Badge variant="preview" className="mr-2">Preview</Badge>
            Preview ({previewFields.length} fields)
          </TabsTrigger>
          <TabsTrigger value="beta">
            <Badge variant="beta" className="mr-2">Beta</Badge>
            Beta ({betaFields.length} fields)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="stable">
          <FieldExplorer 
            fields={stableFields} 
            tier="stable"
            onAskAI={(field) => {
              setSelectedField(field)
              setAiDialogOpen(true)
              setAiAnswer('')
              setAiQuestion('')
            }}
          />
        </TabsContent>
        
        <TabsContent value="preview">
          <FieldExplorer 
            fields={previewFields} 
            tier="preview"
            onAskAI={(field) => {
              setSelectedField(field)
              setAiDialogOpen(true)
              setAiAnswer('')
              setAiQuestion('')
            }}
          />
        </TabsContent>
        
        <TabsContent value="beta">
          <FieldExplorer 
            fields={betaFields} 
            tier="beta"
            onAskAI={(field) => {
              setSelectedField(field)
              setAiDialogOpen(true)
              setAiAnswer('')
              setAiQuestion('')
            }}
          />
        </TabsContent>
      </Tabs>

      <Dialog open={aiDialogOpen} onOpenChange={setAiDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Ask AI about "{selectedField?.name}"
            </DialogTitle>
            <DialogDescription>
              Get AI-powered insights about this field and its impact on your integrations.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium mb-2">Field Details</p>
              <div className="p-3 bg-muted rounded-lg text-sm">
                <p><span className="font-medium">Name:</span> {selectedField?.name}</p>
                <p><span className="font-medium">Type:</span> {selectedField?.type}</p>
                {selectedField?.description && (
                  <p><span className="font-medium">Description:</span> {selectedField?.description}</p>
                )}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Your Question</label>
              <textarea
                className="w-full mt-1 p-3 border rounded-lg text-sm resize-none"
                rows={3}
                placeholder="e.g., What is this field used for? How does it impact Chargebee integrations?"
                value={aiQuestion}
                onChange={(e) => setAiQuestion(e.target.value)}
              />
            </div>

            <div className="flex gap-2">
              <Button onClick={handleAskAI} disabled={aiLoading || !aiQuestion.trim()}>
                {aiLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  'Ask AI'
                )}
              </Button>
              <Button variant="outline" onClick={() => setAiQuestion("What is this field used for?")}>
                Suggest Question
              </Button>
            </div>

            {aiAnswer && (
              <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
                <p className="text-sm font-medium mb-2">AI Response</p>
                <p className="text-sm">{aiAnswer}</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

interface FieldExplorerProps {
  fields: Field[]
  tier: string
  onAskAI: (field: Field) => void
}

function FieldExplorer({ fields, tier, onAskAI }: FieldExplorerProps) {
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
    <Card>
      <CardHeader>
        <CardTitle>Payment Intents</CardTitle>
        <CardDescription>Stripe API object structure for {tier} tier</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px]">
          <div className="space-y-1">
            {fields.map((field) => (
              <FieldRow key={field.name} field={field} depth={0} onAskAI={onAskAI} />
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
  onAskAI: (field: Field) => void
}

function FieldRow({ field, depth, onAskAI }: FieldRowProps) {
  const [expanded, setExpanded] = useState(false)
  const hasChildren = field.children && field.children.length > 0

  return (
    <div>
      <div
        className={`flex items-center gap-2 p-2 rounded hover:bg-muted/50 cursor-pointer group`}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        {hasChildren ? (
          expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
        ) : (
          <div className="w-4" />
        )}
        
        <span className="font-mono text-sm font-medium">{field.name}</span>
        
        <Badge variant="outline" className="text-xs">
          {field.type}
        </Badge>
        
        {field.required && (
          <Badge variant="destructive" className="text-xs">required</Badge>
        )}
        
        {field.deprecated && (
          <Badge variant="secondary" className="text-xs line-through">deprecated</Badge>
        )}

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          className="opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation()
            onAskAI(field)
          }}
        >
          <MessageSquare className="h-3 w-3 mr-1" />
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
            <FieldRow key={child.name} field={child} depth={depth + 1} onAskAI={onAskAI} />
          ))}
        </div>
      )}
    </div>
  )
}
