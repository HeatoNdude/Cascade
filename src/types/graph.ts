export type NodeType = 'function' | 'method' | 'class' | 'module'

export interface GraphNode {
  id: string
  label: string
  type: NodeType
  file: string
  language: string
  line_start?: number
  line_end?: number
  docstring?: string
  params?: string[]
  is_async?: boolean
  primary_author?: string
  last_modified?: string
  last_commit?: string
  bases?: string[]
  methods?: string[]
}

export interface GraphEdge {
  source: string
  target: string
  edge_type: 'contains' | 'imports' | 'calls' | 'inherits'
  is_dynamic?: boolean
  names?: string[]
}

export interface NodeDetail extends GraphNode {
  history: Array<{
    hash: string
    author: string
    date: string
    message: string
  }>
  callers: string[]
  callees: string[]
}

export interface GraphStats {
  nodes: number
  edges: number
  files_parsed: number
  status: string
  repo?: string
}

export interface BuildProgress {
  current: number
  total: number
  current_file: string
  status: string
}

export interface SearchResult {
  node_id: string
  score: number
  name: string
  type: NodeType
  file: string
  docstring: string
}

export const NODE_COLORS: Record<string, string> = {
  function: '#3b82f6',
  method:   '#8b5cf6',
  class:    '#f59e0b',
  module:   '#6b7280',
}

export const EDGE_COLORS: Record<string, string> = {
  contains: '#d1d5db',
  imports:  '#3b82f6',
  calls:    '#22c55e',
  inherits: '#f59e0b',
}
