import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '@/lib/api'
import type { GraphNode, GraphEdge, GraphStats, BuildProgress } from '@/types/graph'

export type GraphStatus = 'idle' | 'building' | 'ready' | 'error'

export interface GraphState {
  status: GraphStatus
  progress: BuildProgress
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats | null
  error: string | null
}

const INITIAL_STATE: GraphState = {
  status:   'idle',
  progress: { current: 0, total: 0, current_file: '', status: 'idle' },
  nodes:    [],
  edges:    [],
  stats:    null,
  error:    null,
}

export function useGraph() {
  const [state, setState] = useState<GraphState>(INITIAL_STATE)
  const pollRef           = useRef<ReturnType<typeof setInterval> | null>(null)
  const wsRef             = useRef<WebSocket | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const loadGraphData = useCallback(async () => {
    try {
      const [nodesRes, edgesRes, statsRes] = await Promise.all([
        api.nodes(undefined, 500),
        api.edges(2000),
        api.graphStats(),
      ])
      setState(prev => ({
        ...prev,
        status: 'ready',
        nodes:  nodesRes.nodes,
        edges:  edgesRes.edges,
        stats:  statsRes,
        error:  null,
      }))
    } catch (e: any) {
      setState(prev => ({
        ...prev,
        status: 'error',
        error:  e.message
      }))
    }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.graphStatus()
        setState(prev => ({
          ...prev,
          progress: res.progress,
          status:   res.status as GraphStatus,
        }))
        if (res.status === 'ready') {
          stopPolling()
          await loadGraphData()
        } else if (res.status.startsWith('error')) {
          stopPolling()
          setState(prev => ({ ...prev, status: 'error', error: res.status }))
        }
      } catch (e) {
        // backend not ready yet, keep polling
      }
    }, 1500)
  }, [stopPolling, loadGraphData])

  const openRepo = useCallback(async (repoPath: string) => {
    setState({ ...INITIAL_STATE, status: 'building' })
    try {
      await api.openRepo(repoPath)
      startPolling()
    } catch (e: any) {
      setState(prev => ({ ...prev, status: 'error', error: e.message }))
    }
  }, [startPolling])

  const refreshGraph = useCallback(async () => {
    if (state.status === 'ready') {
      await loadGraphData()
    }
  }, [state.status, loadGraphData])

  // Connect WebSocket for live updates
  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:5001/ws')
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.event === 'ready') {
          loadGraphData()
        }
      } catch {}
    }

    ws.onerror = () => {} // silent — backend may not be up yet

    // Keep alive ping every 20s
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 20000)

    return () => {
      clearInterval(ping)
      ws.close()
    }
  }, [loadGraphData])

  // Check if a graph is already loaded on mount
  useEffect(() => {
    api.graphStatus().then((res: any) => {
      if (res.status === 'ready') {
        loadGraphData()
      }
    }).catch(() => {})
  }, [loadGraphData])

  useEffect(() => () => stopPolling(), [stopPolling])

  return { state, openRepo, refreshGraph }
}
