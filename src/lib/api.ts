import type {
  GraphNode, GraphEdge, NodeDetail,
  GraphStats, BuildProgress, SearchResult
} from '@/types/graph'

const BASE = 'http://127.0.0.1:5001'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  health: () => get<{ status: string; graph_status: string; repo: string | null }>('/health'),

  openRepo: (repo_path: string) =>
    post<{ status: string }>('/graph/open', { repo_path }),

  graphStatus: () =>
    get<{ status: string; progress: BuildProgress; stats: GraphStats }>('/graph/status'),

  graphStats: () => get<GraphStats>('/graph/stats'),

  nodes: (type?: string, limit = 500) =>
    get<{ nodes: GraphNode[]; total: number }>(
      `/graph/nodes${type ? `?type=${type}&limit=${limit}` : `?limit=${limit}`}`
    ),

  edges: (limit = 2000) =>
    get<{ edges: GraphEdge[]; total: number }>(`/graph/edges?limit=${limit}`),

  node: (id: string) =>
    get<{ id: string; data: NodeDetail; callers: string[]; callees: string[] }>(
      `/graph/node/${encodeURIComponent(id)}`
    ),

  search: (query: string, top_k = 10) =>
    post<{ results: SearchResult[] }>('/graph/search', { query, top_k }),
}
