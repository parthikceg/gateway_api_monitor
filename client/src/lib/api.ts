const API_BASE = '/api'

export interface Change {
  id: string
  type: string
  field: string
  severity: string
  category: string
  maturity: string | null
  tier: string
  summary: string | null
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
  
  getChanges: (params?: { limit?: number; severity?: string; tier?: string; maturity?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.severity) searchParams.set('severity', params.severity)
    if (params?.tier) searchParams.set('tier', params.tier)
    if (params?.maturity) searchParams.set('maturity', params.maturity)
    const query = searchParams.toString()
    return fetchApi<{ changes: Change[] }>(`/changes${query ? `?${query}` : ''}`)
  },
  
  getSnapshots: (params?: { limit?: number; tier?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.tier) searchParams.set('tier', params.tier)
    const query = searchParams.toString()
    return fetchApi<{ snapshots: Snapshot[] }>(`/snapshots${query ? `?${query}` : ''}`)
  },
  
  getSnapshotDetail: (id: string) => fetchApi<Snapshot>(`/snapshots/${id}`),
  
  getSnapshotStats: () => fetchApi<{ stats: { tier: string; count: number }[] }>('/snapshots/stats'),
  
  compareTiers: (source: string, target: string = 'stable') =>
    fetchApi<{ source: string; target: string; changes: unknown[]; upcoming_features_count: number }>(
      `/monitor/compare?source=${source}&target=${target}`
    ),
  
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
