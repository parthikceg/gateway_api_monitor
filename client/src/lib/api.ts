// Determine API base URL based on environment
// - Replit/local: uses /api prefix (FastAPI root_path="/api")
// - AWS EB: no prefix needed (FastAPI root_path="")
const isAWS = window.location.hostname.includes('elasticbeanstalk') ||
              window.location.hostname.includes('amazonaws')
const API_BASE = isAWS ? '' : '/api'

export interface Change {
  id: string
  type: string
  field: string
  endpoint?: string
  severity: string
  category: string
  maturity: string | null
  tier: string
  summary: string | null
  old_value: string | null
  new_value: string | null
  detected_at: string
}

export interface Snapshot {
  id: string
  gateway: string
  endpoint: string
  tier: string
  created_at: string
  spec_url?: string
  schema_data?: Record<string, unknown>
}

export interface HealthStatus {
  status: string
  service: string
  version: string
  tiers: string[]
  monitored_endpoints?: string[]
}

export interface EndpointsResponse {
  gateway: string
  endpoints: string[]
  count: number
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }
  
  return response.json()
}

export const api = {
  getHealth: () => fetchApi<HealthStatus>('/'),

  getEndpoints: () => fetchApi<EndpointsResponse>('/endpoints'),

  getChanges: (params?: { limit?: number; offset?: number; severity?: string; tier?: string; maturity?: string; endpoint?: string; schema_type?: string; date_from?: string; date_to?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    if (params?.severity) searchParams.set('severity', params.severity)
    if (params?.tier) searchParams.set('tier', params.tier)
    if (params?.maturity) searchParams.set('maturity', params.maturity)
    if (params?.endpoint) searchParams.set('endpoint', params.endpoint)
    if (params?.schema_type) searchParams.set('schema_type', params.schema_type)
    if (params?.date_from) searchParams.set('date_from', params.date_from)
    if (params?.date_to) searchParams.set('date_to', params.date_to)
    const query = searchParams.toString()
    return fetchApi<{ changes: Change[]; total: number; offset: number; limit: number; has_more: boolean }>(`/changes${query ? `?${query}` : ''}`)
  },
  
  getSnapshots: (params?: { limit?: number; tier?: string; endpoint?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.tier) searchParams.set('tier', params.tier)
    if (params?.endpoint) searchParams.set('endpoint', params.endpoint)
    const query = searchParams.toString()
    return fetchApi<{ snapshots: Snapshot[] }>(`/snapshots${query ? `?${query}` : ''}`)
  },
  
  getSnapshotDetail: (id: string) => fetchApi<Snapshot>(`/snapshots/${id}`),
  
  getSnapshotStats: () => fetchApi<{ stats: { tier: string; count: number }[] }>('/snapshots/stats'),
  
  compareTiers: (source: string, target: string = 'stable', endpoint?: string) => {
    const params = new URLSearchParams({ source, target })
    if (endpoint) params.set('endpoint', endpoint)
    return fetchApi<{ source: string; target: string; changes: unknown[]; upcoming_features_count: number }>(
      `/monitor/compare?${params.toString()}`
    )
  },
  
  runMonitoring: (tier?: string) => 
    fetchApi<{ status: string; message?: string }>(`/monitor/run${tier ? `?tier=${tier}` : ''}`, { method: 'POST' }),

  askAI: async (question: string, context: Record<string, unknown>) => {
    return fetchApi<{ answer: string }>('/ai/ask', {
      method: 'POST',
      body: JSON.stringify({ question, context }),
    })
  },

  subscribe: async (data: { name: string; email: string }) => {
    return fetchApi<{ status: string; message: string }>('/subscribe', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  getFieldAvailability: async () => {
    return fetchApi<{ 
      beta_only: string[]
      preview_only: string[]
      stable: string[]
    }>('/fields/availability')
  },
}
