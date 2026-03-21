'use client'
import { useState, useRef, useCallback } from 'react'
import { Zap, ChevronDown, ChevronUp } from 'lucide-react'

export interface SimResult {
  seed_node_ids:   string[]
  affected_nodes:  AffectedNodeResult[]
  affected_tests:  { name: string; file: string }[]
  report_markdown: string
  mermaid_graph:   string
  total_breaks:    number
  confidence_score:number
  elapsed_ms:      number
}

export interface AffectedNodeResult {
  node_id:      string
  name:         string
  file:         string
  risk_label:   'red' | 'amber' | 'green'
  risk_score:   number
  hop_distance: number
  is_dynamic_path: boolean
  break_reason: string
  history_note: string
}

interface Props {
  repoPath: string | null
  onBlastRadius: (seedIds: string[], affected: AffectedNodeResult[]) => void
  onClear: () => void
}

const RISK_COLORS = {
  red:   { dot: '#ef4444', bg: '#7f1d1d22', border: '#ef444433' },
  amber: { dot: '#f59e0b', bg: '#78350f22', border: '#f59e0b33' },
  green: { dot: '#22c55e', bg: '#14532d22', border: '#22c55e33' },
}

export default function SimulationPanel({ repoPath, onBlastRadius, onClear }: Props) {
  const [prompt,   setPrompt]   = useState('')
  const [stage,    setStage]    = useState('')
  const [running,  setRunning]  = useState(false)
  const [result,   setResult]   = useState<SimResult | null>(null)
  const [error,    setError]    = useState('')
  const [expanded, setExpanded] = useState(true)
  const [showMermaid, setShowMermaid] = useState(false)
  const [copied,   setCopied]   = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const runSim = useCallback(async () => {
    if (!prompt.trim() || running) return
    setRunning(true)
    setError('')
    setResult(null)
    setStage('Starting…')
    onClear()

    abortRef.current = new AbortController()

    try {
      const resp = await fetch('http://127.0.0.1:5001/simulate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ prompt, repo_path: repoPath }),
        signal:  abortRef.current.signal,
      })

      console.log('[Sim] fetch status:', resp.status, resp.headers.get('content-type'))

      if (!resp.ok) {
        const errText = await resp.text()
        console.error('[Sim] Non-OK response:', errText)
        setError(`Server error ${resp.status}: ${errText}`)
        setStage('')
        return
      }

      if (!resp.body) {
        setError('No response body — streaming not supported')
        setStage('')
        return
      }

      const reader  = resp.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''
      let   currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          console.log('[Sim] Stream ended')
          break
        }
        const text = decoder.decode(value, { stream: true })
        console.log('[Sim] chunk:', text.slice(0, 120))
        buffer += text

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.replace('event: ', '').trim()
            console.log('[Sim] event:', currentEvent)
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (currentEvent === 'stage') {
                setStage(data.message)
              } else if (currentEvent === 'blast_radius') {
                onBlastRadius(data.seed_node_ids, data.affected_nodes)
              } else if (currentEvent === 'complete') {
                setResult(data as SimResult)
                setStage('')
              } else if (currentEvent === 'error') {
                setError(data.message)
                setStage('')
              }
            } catch (parseErr) {
              console.warn('[Sim] JSON parse error:', parseErr, 'line:', line.slice(0, 80))
            }
          }
        }
      }

      // Re-parse complete event from full buffer if needed
      const completeMatch = buffer.match(/event: complete\ndata: (.+)/)
      if (completeMatch) {
        try {
          const data = JSON.parse(completeMatch[1])
          setResult(data)
          onBlastRadius(data.seed_node_ids, data.affected_nodes)
        } catch {}
      }

    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e.message ?? 'Simulation failed')
      }
      setStage('')
    } finally {
      setRunning(false)
    }
  }, [prompt, running, repoPath, onBlastRadius, onClear])

  const cancel = () => {
    abortRef.current?.abort()
    setRunning(false)
    setStage('')
  }

  const copyMermaid = () => {
    if (result?.mermaid_graph) {
      navigator.clipboard.writeText(result.mermaid_graph)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const riskGroups = result ? {
    red:   result.affected_nodes.filter(n => n.risk_label === 'red'),
    amber: result.affected_nodes.filter(n => n.risk_label === 'amber'),
    green: result.affected_nodes.filter(n => n.risk_label === 'green'),
  } : null

  return (
    <div style={{
      position:      'absolute',
      bottom:        0,
      left:          0,
      right:         0,
      background:    '#0a1628',
      borderTop:     '1px solid #1e293b',
      fontFamily:    'monospace',
      zIndex:        15,
      maxHeight:     expanded ? '55vh' : '48px',
      transition:    'max-height 0.25s ease',
      overflow:      'hidden',
      display:       'flex',
      flexDirection: 'column',
    }}>

      {/* Header bar */}
      <div style={{
        display:        'flex',
        alignItems:     'center',
        gap:            '10px',
        padding:        '10px 14px',
        borderBottom:   expanded ? '1px solid #1e293b' : 'none',
        flexShrink:     0,
        cursor:         'pointer',
      }} onClick={() => !running && setExpanded(p => !p)}>
        <Zap size={13} color="#3b82f6" />
        <span style={{ color: '#94a3b8', fontSize: '12px', fontWeight: 500 }}>
          Simulate
        </span>

        {stage && (
          <span style={{
            fontSize:  '11px',
            color:     '#3b82f6',
            animation: 'pulse 1.5s infinite',
          }}>
            {stage}
          </span>
        )}

        {result && !running && (
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            {result.total_breaks} breaks · {result.elapsed_ms}ms ·{' '}
            confidence {Math.round(result.confidence_score * 100)}%
          </span>
        )}

        <div style={{ flex: 1 }} />
        {expanded
          ? <ChevronDown size={13} color="#475569" />
          : <ChevronUp   size={13} color="#475569" />
        }
      </div>

      {/* Input row */}
      <div style={{
        display:   'flex',
        gap:       '8px',
        padding:   '10px 14px',
        flexShrink: 0,
      }}>
        <input
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && runSim()}
          placeholder='What if… "replace Redis with Dragonfly" or "rename parse_file to parse_source"'
          disabled={running}
          style={{
            flex:         1,
            background:   '#0d1f35',
            border:       '1px solid #1e293b',
            borderRadius: '6px',
            padding:      '8px 12px',
            color:        '#e2e8f0',
            fontSize:     '12px',
            fontFamily:   'monospace',
            outline:      'none',
          }}
        />
        <button
          onClick={running ? cancel : runSim}
          disabled={!running && !prompt.trim()}
          style={{
            padding:      '8px 16px',
            background:   running ? '#7f1d1d' : '#1d4ed8',
            border:       'none',
            borderRadius: '6px',
            color:        '#fff',
            fontSize:     '12px',
            fontFamily:   'monospace',
            cursor:       'pointer',
            flexShrink:   0,
          }}
        >
          {running ? 'Cancel' : '⚡ Run'}
        </button>
      </div>

      {error && (
        <div style={{
          margin:       '0 14px 10px',
          padding:      '8px 12px',
          background:   '#7f1d1d22',
          border:       '1px solid #ef444433',
          borderRadius: '6px',
          color:        '#fca5a5',
          fontSize:     '12px',
        }}>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{
          flex:      1,
          overflowY: 'auto',
          padding:   '0 14px 14px',
          display:   'flex',
          gap:       '12px',
        }}>

          {/* Left: affected nodes */}
          <div style={{ flex: '0 0 320px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {(['red', 'amber', 'green'] as const).map(label => {
              const nodes = riskGroups![label]
              if (!nodes.length) return null
              const c = RISK_COLORS[label]
              return (
                <div key={label}>
                  <div style={{
                    fontSize:     '10px',
                    color:        c.dot,
                    marginBottom: '5px',
                    textTransform:'uppercase',
                    letterSpacing:'0.08em',
                  }}>
                    {label === 'red' ? '🔴' : label === 'amber' ? '🟡' : '🟢'}{' '}
                    {label} risk ({nodes.length})
                  </div>
                  {nodes.slice(0, 6).map(n => (
                    <div key={n.node_id} style={{
                      background:   c.bg,
                      border:       `1px solid ${c.border}`,
                      borderRadius: '5px',
                      padding:      '6px 9px',
                      marginBottom: '4px',
                    }}>
                      <div style={{
                        color:    '#e2e8f0',
                        fontSize: '11.5px',
                        fontWeight: 500,
                      }}>
                        {n.name}
                      </div>
                      <div style={{ color: '#475569', fontSize: '10px', marginBottom: '3px' }}>
                        {n.file.split('/').pop()} · hop {n.hop_distance}
                        {n.is_dynamic_path ? ' · ⚠ dynamic' : ''}
                      </div>
                      <div style={{ color: '#64748b', fontSize: '10.5px', lineHeight: 1.5 }}>
                        {n.break_reason}
                      </div>
                      {n.history_note && (
                        <div style={{
                          marginTop:  '4px',
                          color:      '#334155',
                          fontSize:   '10px',
                          fontStyle:  'italic',
                        }}>
                          ↺ {n.history_note.slice(0, 80)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )
            })}

            {/* Tests at risk */}
            {result.affected_tests.length > 0 && (
              <div>
                <div style={{
                  fontSize:     '10px',
                  color:        '#7dd3fc',
                  marginBottom: '5px',
                  textTransform:'uppercase',
                  letterSpacing:'0.08em',
                }}>
                  🧪 tests at risk ({result.affected_tests.length})
                </div>
                {result.affected_tests.slice(0, 5).map((t, i) => (
                  <div key={i} style={{
                    color:     '#64748b',
                    fontSize:  '11px',
                    padding:   '3px 0',
                    borderBottom: '1px solid #0f172a',
                  }}>
                    {t.name} <span style={{ color: '#334155' }}>{t.file.split('/').pop()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right: report */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              display:        'flex',
              justifyContent: 'space-between',
              alignItems:     'center',
              marginBottom:   '8px',
            }}>
              <div style={{ fontSize: '10px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Impact Report
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={() => setShowMermaid(p => !p)}
                  style={{
                    background: 'none', border: '1px solid #1e293b',
                    borderRadius: '4px', padding: '3px 8px',
                    color: '#475569', fontSize: '10px', cursor: 'pointer',
                    fontFamily: 'monospace',
                  }}
                >
                  {showMermaid ? 'Report' : 'Mermaid'}
                </button>
                <button
                  onClick={copyMermaid}
                  style={{
                    background: 'none', border: '1px solid #1e293b',
                    borderRadius: '4px', padding: '3px 8px',
                    color: copied ? '#22c55e' : '#475569',
                    fontSize: '10px', cursor: 'pointer',
                    fontFamily: 'monospace',
                  }}
                >
                  {copied ? '✓ Copied' : 'Copy Mermaid'}
                </button>
              </div>
            </div>

            <div style={{
              background:   '#080f1a',
              border:       '1px solid #1e293b',
              borderRadius: '6px',
              padding:      '12px',
              fontSize:     '11.5px',
              color:        '#94a3b8',
              lineHeight:   1.7,
              overflowY:    'auto',
              maxHeight:    '280px',
              whiteSpace:   showMermaid ? 'pre' : 'pre-wrap',
              fontFamily:   'monospace',
            }}>
              {showMermaid ? result.mermaid_graph : result.report_markdown}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
