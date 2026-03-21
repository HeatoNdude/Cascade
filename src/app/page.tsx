'use client'
import { useState, useMemo, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { useGraph } from '@/hooks/useGraph'
import NodeInspector from '@/components/NodeInspector'
import SearchBar from '@/components/SearchBar'
import FilterBar from '@/components/FilterBar'
import RepoPicker from '@/components/RepoPicker'
import { RefreshCw, FolderOpen, Zap } from 'lucide-react'
import SimulationPanel, { type AffectedNodeResult } from '@/components/SimulationPanel'

// Dynamic import to avoid SSR issues with Cytoscape
const GraphView = dynamic(() => import('@/components/GraphView'), {
  ssr: false,
  loading: () => (
    <div style={{
      width: '100%', height: '100%',
      display: 'flex', alignItems: 'center',
      justifyContent: 'center', color: '#334155',
      fontFamily: 'monospace', fontSize: '13px',
      background: '#080f1a',
    }}>
      Loading graph renderer…
    </div>
  )
})

const ALL_TYPES = new Set(['function', 'method', 'class', 'module'])

export default function GodView() {
  const { state, openRepo, refreshGraph } = useGraph()

  const [selectedId,   setSelectedId]   = useState<string | null>(null)
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set())
  const [activeTypes,  setActiveTypes]  = useState<Set<string>>(new Set(ALL_TYPES))
  const [showPicker]            = useState(false)

  const [blastSeedIds,    setBlastSeedIds]    = useState<string[]>([])
  const [blastAffected,   setBlastAffected]   = useState<AffectedNodeResult[]>([])
  const [simHighlightIds, setSimHighlightIds] = useState<Set<string>>(new Set())

  const isReady    = state.status === 'ready'
  const isBuilding = state.status === 'building'

  // Filter nodes by active types
  const filteredNodes = useMemo(() =>
    state.nodes.filter(n => activeTypes.has(n.type)),
    [state.nodes, activeTypes]
  )

  // Filter edges to only reference visible nodes
  const visibleNodeIds = useMemo(() =>
    new Set(filteredNodes.map(n => n.id)),
    [filteredNodes]
  )

  const filteredEdges = useMemo(() =>
    state.edges.filter(e =>
      visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
    ),
    [state.edges, visibleNodeIds]
  )

  const toggleType = (type: string) => {
    setActiveTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) {
        if (next.size === 1) return prev // keep at least one
        next.delete(type)
      } else {
        next.add(type)
      }
      return next
    })
  }

  const handleNodeClick = (id: string) => {
    setSelectedId(id || null)
    setHighlightIds(new Set())
  }

  const handleSearchSelect = (nodeId: string) => {
    if (!nodeId) {
      setSelectedId(null)
      setHighlightIds(new Set())
      return
    }
    setSelectedId(nodeId)
    setHighlightIds(new Set([nodeId]))
  }

  const handleBlastRadius = useCallback((
    seedIds: string[],
    affected: AffectedNodeResult[]
  ) => {
    setBlastSeedIds(seedIds)
    setBlastAffected(affected)
    // Build highlight map with risk colors for GraphView
    const ids = new Set([
      ...seedIds,
      ...affected.map(n => n.node_id)
    ])
    setSimHighlightIds(ids)
  }, [])

  const handleSimClear = useCallback(() => {
    setBlastSeedIds([])
    setBlastAffected([])
    setSimHighlightIds(new Set())
  }, [])

  // Show repo picker if no graph loaded yet
  if (!isReady && !isBuilding && !showPicker) {
    return (
      <RepoPicker
        onOpen={(p) => { openRepo(p) }}
        isBuilding={false}
        progress={state.progress}
      />
    )
  }

  if (isBuilding) {
    return (
      <RepoPicker
        onOpen={openRepo}
        isBuilding={true}
        progress={state.progress}
      />
    )
  }

  return (
    <div style={{
      width:     '100vw',
      height:    '100vh',
      display:   'flex',
      flexDirection: 'column',
      background:'#080f1a',
      overflow:  'hidden',
    }}>
      {/* Top bar */}
      <div style={{
        display:        'flex',
        alignItems:     'center',
        gap:            '12px',
        padding:        '8px 14px',
        background:     '#0a1628',
        borderBottom:   '1px solid #1e293b',
        flexShrink:     0,
        zIndex:         10,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '6px' }}>
          <Zap size={15} color="#3b82f6" />
          <span style={{ color: '#e2e8f0', fontSize: '13px', fontWeight: 500, fontFamily: 'monospace' }}>
            cascade
          </span>
        </div>

        {/* Repo path */}
        {state.stats?.repo && (
          <div style={{
            color:        '#334155',
            fontSize:     '11px',
            fontFamily:   'monospace',
            overflow:     'hidden',
            textOverflow: 'ellipsis',
            whiteSpace:   'nowrap',
            maxWidth:     '220px',
          }}>
            {state.stats.repo}
          </div>
        )}

        <div style={{ flex: 1 }} />

        {/* Search */}
        <SearchBar onSelect={handleSearchSelect} />

        {/* Filter bar */}
        <FilterBar
          activeTypes={activeTypes}
          onToggle={toggleType}
          stats={state.stats ? {
            nodes: filteredNodes.length,
            edges: filteredEdges.length
          } : null}
        />

        {/* Actions */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={refreshGraph}
            title="Refresh graph"
            style={{
              background:   'none',
              border:       '1px solid #1e293b',
              borderRadius: '5px',
              padding:      '5px 8px',
              cursor:       'pointer',
              color:        '#475569',
              display:      'flex',
              alignItems:   'center',
            }}
          >
            <RefreshCw size={13} />
          </button>
          <button
            onClick={() => openRepo('')}
            title="Open another repo"
            style={{
              background:   'none',
              border:       '1px solid #1e293b',
              borderRadius: '5px',
              padding:      '5px 8px',
              cursor:       'pointer',
              color:        '#475569',
              display:      'flex',
              alignItems:   'center',
            }}
          >
            <FolderOpen size={13} />
          </button>
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {isReady && (
          <GraphView
            nodes={filteredNodes}
            edges={filteredEdges}
            selectedId={selectedId}
            highlightIds={simHighlightIds.size > 0 ? simHighlightIds : highlightIds}
            blastAffected={blastAffected}
            onNodeClick={handleNodeClick}
          />
        )}

        {isReady && (
          <NodeInspector
            nodeId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}

        {isReady && (
          <SimulationPanel
            repoPath={state.stats?.repo ?? null}
            onBlastRadius={handleBlastRadius}
            onClear={handleSimClear}
          />
        )}

        {/* Status bar */}
        <div style={{
          position:   'absolute',
          bottom:     '10px',
          left:       '12px',
          fontFamily: 'monospace',
          fontSize:   '10px',
          color:      '#1e3a5f',
          pointerEvents: 'none',
        }}>
          {state.status === 'error' && (
            <span style={{ color: '#7f1d1d' }}>
              Error: {state.error}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
