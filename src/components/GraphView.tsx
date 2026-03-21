'use client'
import { useEffect, useRef, useCallback } from 'react'
import type { GraphNode, GraphEdge } from '@/types/graph'
import { NODE_COLORS, EDGE_COLORS } from '@/types/graph'
import type { AffectedNodeResult } from './SimulationPanel'

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedId: string | null
  highlightIds?: Set<string>
  blastAffected?: AffectedNodeResult[]
  onNodeClick: (id: string) => void
}

// Derive module id from any node id
// Node id format: "path/to/file.py::FunctionName"
// Module id format: "path/to/file.py::__module__"
function getModuleId(nodeId: string): string {
  const sep = nodeId.lastIndexOf('::')
  if (sep === -1) return ''
  return nodeId.slice(0, sep) + '::__module__'
}

export default function GraphView({
  nodes, edges, selectedId, highlightIds,
  blastAffected = [], onNodeClick
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef        = useRef<any>(null)

  const buildElements = useCallback(() => {
    // Separate modules and children
    const moduleIds = new Set(
      nodes
        .filter(n => n.type === 'module')
        .map(n => n.id)
    )

    // Module nodes (compound parents — no parent attr)
    const cyModules = nodes
      .filter(n => n.type === 'module')
      .map(n => ({
        data: {
          id:    n.id,
          label: n.label,
          type:  'module',
          color: '#1e293b',
        }
      }))

    // Child nodes (functions, methods, classes)
    const cyChildren = nodes
      .filter(n => n.type !== 'module')
      .map(n => {
        const parentId = getModuleId(n.id)
        return {
          data: {
            id:     n.id,
            label:  n.label.length > 16
                      ? n.label.slice(0, 14) + '…'
                      : n.label,
            type:   n.type,
            color:  NODE_COLORS[n.type] ?? '#94a3b8',
            // Only set parent if the module actually exists
            ...(moduleIds.has(parentId) ? { parent: parentId } : {})
          }
        }
      })

    // Edges: only imports and calls between modules,
    // skip contains entirely
    const edgeSet = new Set<string>()
    const cyEdges = edges
      .filter(e => e.edge_type !== 'contains')
      .filter(e => {
        const key = `${e.source}→${e.target}`
        if (edgeSet.has(key)) return false
        edgeSet.add(key)
        return true
      })
      .map((e, i) => ({
        data: {
          id:        `e${i}`,
          source:    e.source,
          target:    e.target,
          edge_type: e.edge_type,
          color:     EDGE_COLORS[e.edge_type] ?? '#334155',
        }
      }))

    // Put modules first so children can reference them
    return [...cyModules, ...cyChildren, ...cyEdges]
  }, [nodes, edges])

  const getStyle = useCallback(() => [
    // ── Compound parent (module) ──────────────────
    {
      selector: '$node > node',
      style: {
        'padding':           '14px',
      }
    },
    {
      selector: 'node[type = "module"]',
      style: {
        'background-color':        '#0d1f35',
        'background-opacity':      '0.85',
        'border-color':            '#334155',
        'border-width':            '1.5px',
        'border-opacity':          '1',
        'label':                   'data(label)',
        'font-size':               '11px',
        'font-family':             'monospace',
        'font-weight':             '500',
        'color':                   '#64748b',
        'text-valign':             'top',
        'text-halign':             'center',
        'text-margin-y':           '-6px',
        'text-background-color':   '#080f1a',
        'text-background-opacity': '0.9',
        'text-background-padding': '3px',
        'shape':                   'round-rectangle',
        'corner-radius':           '8px',
      }
    },
    // ── Child nodes ───────────────────────────────
    {
      selector: 'node[type != "module"]',
      style: {
        'background-color':        'data(color)',
        'label':                   '',
        'width':                   '16px',
        'height':                  '16px',
        'border-width':            '1px',
        'border-color':            'data(color)',
        'border-opacity':          '0.6',
        'font-size':               '10px',
        'font-family':             'monospace',
        'color':                   '#cbd5e1',
        'text-valign':             'bottom',
        'text-halign':             'center',
        'text-margin-y':           '5px',
        'text-background-color':   '#080f1a',
        'text-background-opacity': 0.85,
        'text-background-padding': 3,
        'text-background-shape':   'roundrectangle',
        'text-wrap':               'none',
      }
    },
    {
      selector: 'node[type = "class"]',
      style: {
        'shape':  'diamond',
        'width':  '18px',
        'height': '18px',
      }
    },
    // Hover label overlay
    {
      selector: 'node.hover-label',
      style: {
        'label': 'data(label)',
        'z-index': 9999,
      }
    },
    // ── Simulation Blast Radius ────────────────────
    {
      selector: 'node.blast-seed',
      style: {
        'background-color': '#60a5fa',
        'border-color':     '#2563eb',
        'border-width':     '3px',
        'border-opacity':   1,
        'opacity':          1,
        'underlay-color':   '#3b82f6',
        'underlay-padding': 14,
        'underlay-opacity': 0.9,
        'underlay-shape':   'ellipse',
        'width':            '24px',
        'height':           '24px',
        'transition-property': 'underlay-padding, underlay-opacity',
        'transition-duration': '900ms',
        'transition-timing-function': 'ease-in-out',
        'z-index': 900,
      }
    },
    {
      selector: 'node.pulse-active',
      style: {
        'underlay-padding': 20,
        'underlay-opacity': 1,
      }
    },
    {
      selector: 'node.blast-seed[type = "class"]',
      style: {
        'width': '26px',
        'height': '26px',
      }
    },
    {
      selector: 'node.blast-affected-red',
      style: {
        'background-color': '#ef4444',
        'border-color':     '#ef4444',
        'border-width':     '3px',
        'border-opacity':   1,
        'opacity':          1,
        'underlay-color':   '#ef4444',
        'underlay-padding': 8,
        'underlay-opacity': 0.7,
        'underlay-shape':   'ellipse',
        'width':            '16px',
        'height':           '16px',
        'z-index': 800,
      }
    },
    {
      selector: 'node.blast-affected-red[type = "class"]',
      style: { 'width': '18px', 'height': '18px' }
    },
    {
      selector: 'node.blast-affected-amber',
      style: {
        'background-color': '#f59e0b',
        'border-color':     '#f59e0b',
        'border-width':     '3px',
        'border-opacity':   1,
        'opacity':          1,
        'underlay-color':   '#f59e0b',
        'underlay-padding': 8,
        'underlay-opacity': 0.7,
        'underlay-shape':   'ellipse',
        'width':            '16px',
        'height':           '16px',
        'z-index': 800,
      }
    },
    {
      selector: 'node.blast-affected-amber[type = "class"]',
      style: { 'width': '18px', 'height': '18px' }
    },
    {
      selector: 'node.blast-affected-green',
      style: {
        'background-color': '#22c55e',
        'border-color':     '#22c55e',
        'border-width':     '3px',
        'border-opacity':   1,
        'opacity':          1,
        'underlay-color':   '#22c55e',
        'underlay-padding': 8,
        'underlay-opacity': 0.7,
        'underlay-shape':   'ellipse',
        'width':            '16px',
        'height':           '16px',
        'z-index': 800,
      }
    },
    {
      selector: 'node.blast-affected-green[type = "class"]',
      style: { 'width': '18px', 'height': '18px' }
    },
    // ── Selection / highlight ─────────────────────
    {
      selector: 'node:selected',
      style: {
        'border-width':   '3px',
        'border-color':   '#f1f5f9',
        'border-opacity': '1',
        'label':          'data(label)',
      }
    },
    {
      selector: 'node.highlighted',
      style: {
        'border-width':   '2.5px',
        'border-color':   '#fbbf24',
        'border-opacity': '1',
        'label':          'data(label)',
      }
    },
    {
      selector: 'node.dimmed',
      style: { 'opacity': '0.12' }
    },
    // ── Edges ─────────────────────────────────────
    {
      selector: 'edge',
      style: {
        'width':              '1.2px',
        'line-color':         'data(color)',
        'target-arrow-color': 'data(color)',
        'target-arrow-shape': 'triangle',
        'arrow-scale':        '0.65',
        'curve-style':        'bezier',
        'opacity':            '0.55',
      }
    },
    {
      selector: 'edge[edge_type = "imports"]',
      style: {
        'line-style': 'dashed',
        'opacity':    '0.45',
      }
    },
    {
      selector: 'edge[edge_type = "calls"]',
      style: {
        'opacity':  '0.7',
        'width':    '1.5px',
      }
    },
    {
      selector: 'edge.dimmed',
      style: { 'opacity': '0.04' }
    },
  ], [])

  const runLayout = useCallback((cy: any, animate: boolean) => {
    cy.layout({
      name:              'fcose',
      animate:           animate,
      animationDuration: animate ? 900 : 0,
      randomize:         true,

      // High repulsion so compound nodes spread out
      nodeRepulsion:     (node: any) =>
        node.data('type') === 'module' ? 80000 : 4500,
      idealEdgeLength:   (edge: any) =>
        edge.data('edge_type') === 'imports' ? 200 : 80,
      edgeElasticity:    (edge: any) =>
        edge.data('edge_type') === 'imports' ? 0.05 : 0.45,

      nodeSeparation:    80,
      numIter:           6000,
      fit:               true,
      padding:           60,
      gravityRange:      3.5,
      gravity:           0.3,
      gravityCompound:   1.0,
      gravityRangeCompound: 1.5,
      piTol:             0.0000001,
      samplingType:      true,
      sampleSize:        25,
      nestingFactor:     0.1,
      nodeDimensionsIncludeLabels: false,
      uniformNodeDimensions:       false,
      packComponents:    true,
    } as any).run()
  }, [])

  // Init Cytoscape
  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    let cy: any = null

    const init = async () => {
      const [cytoscape, fcose] = await Promise.all([
        import('cytoscape'),
        import('cytoscape-fcose'),
      ])

      try { cytoscape.default.use(fcose.default) } catch {}

      cy = cytoscape.default({
        container:        containerRef.current,
        elements:         buildElements(),
        style:            getStyle(),
        layout:           { name: 'preset' },
        wheelSensitivity: 0.25,
        minZoom:          0.08,
        maxZoom:          4,
      })

      // Click node
      cy.on('tap', 'node', (evt: any) => {
        const n = evt.target
        if (n.data('type') !== 'module') {
          onNodeClick(n.id())
        }
      })

      // Click module label → select module
      cy.on('tap', 'node[type = "module"]', (evt: any) => {
        onNodeClick(evt.target.id())
      })

      // Click background → deselect
      cy.on('tap', (evt: any) => {
        if (evt.target === cy) onNodeClick('')
      })

      // Hover: show label on child nodes, with high z-index
      cy.on('mouseover', 'node', (evt: any) => {
        const n = evt.target
        if (n.data('type') !== 'module') {
          n.addClass('hover-label')
        }
      })

      cy.on('mouseout', 'node', (evt: any) => {
        const n = evt.target
        n.removeClass('hover-label')
      })

      cyRef.current = cy
      runLayout(cy, true)
    }

    init()

    return () => {
      if (cy) cy.destroy()
      cyRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length > 0])

  // Update elements when data changes
  useEffect(() => {
    if (!cyRef.current || nodes.length === 0) return
    cyRef.current.elements().remove()
    cyRef.current.add(buildElements())
    runLayout(cyRef.current, true)
  }, [nodes, edges, buildElements, runLayout])

  // Unified highlight / blast radius coloring
  useEffect(() => {
    if (!cyRef.current) return
    const cy = cyRef.current

    // Reset all visual classes and overrides
    cy.elements().removeClass('highlighted dimmed blast-seed blast-affected-red blast-affected-amber blast-affected-green pulse-active hover-label')
    cy.nodes().removeStyle('opacity')

    let pulseInterval: any;

    // ── Blast radius mode ────────────────────────────────
    if (blastAffected.length > 0) {
      const affectedMap = new Map(
        blastAffected.map(n => [n.node_id, n.risk_label])
      )
      // Build set of seed IDs from highlightIds (seeds + affected)
      const seedIds = highlightIds
        ? new Set([...highlightIds].filter(id => !affectedMap.has(id)))
        : new Set<string>()

      cy.nodes().forEach((node: any) => {
        const nid = node.id()
        const riskLabel = affectedMap.get(nid)

        if (riskLabel) {
          // Affected node — apply risk-specific class
          if (riskLabel === 'red') node.addClass('blast-affected-red')
          else if (riskLabel === 'amber') node.addClass('blast-affected-amber')
          else node.addClass('blast-affected-green')
          
          // CRITICAL: Ensure parent module is NOT dimmed
          const parent = node.parent()
          if (parent.length) {
            parent.style({ 'opacity': '1' })
          }
        } else if (seedIds.has(nid)) {
          // Seed node — dynamic pulsing blue glow
          node.addClass('blast-seed')

          const parent = node.parent()
          if (parent.length) {
            parent.style({ 'opacity': '1' })
          }
        } else {
          // Unaffected node — dim it
          if (node.style('opacity') !== '1') {
            node.style({ 'opacity': '0.15' })
          }
        }
      })

      // Dim all edges
      cy.edges().style({ 'opacity': '0.06' })

      // Animate seed nodes safely using a single interval
      pulseInterval = setInterval(() => {
        if (cyRef.current) cyRef.current.nodes('.blast-seed').toggleClass('pulse-active')
      }, 900)

    } else {
      // ── Normal highlight mode (search / selection) ───────
      if (highlightIds && highlightIds.size > 0) {
        cy.nodes().forEach((n: any) => {
          if (highlightIds.has(n.id())) n.addClass('highlighted')
          else n.addClass('dimmed')
        })
        cy.edges().addClass('dimmed')
      }
    }

    // Cleanup interval to prevent overlapping animations
    return () => {
      if (pulseInterval) clearInterval(pulseInterval)
    }


    if (selectedId) {
      const sel = cy.getElementById(selectedId)
      if (sel.length) {
        const neighborhood = sel.neighborhood().add(sel)
        const parent       = sel.parent()
        const toKeep       = neighborhood.add(parent)
        cy.elements().not(toKeep).addClass('dimmed')
      }
    }
  }, [selectedId, highlightIds, blastAffected])

  return (
    <div
      ref={containerRef}
      style={{
        width:      '100%',
        height:     '100%',
        background: '#080f1a',
      }}
    />
  )
}
