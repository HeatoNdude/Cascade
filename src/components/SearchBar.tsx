'use client'
import { useState, useRef, useCallback } from 'react'
import { api } from '@/lib/api'
import { NODE_COLORS } from '@/types/graph'
import type { SearchResult } from '@/types/graph'
import { Search, X } from 'lucide-react'

interface Props {
  onSelect: (nodeId: string) => void
}

export default function SearchBar({ onSelect }: Props) {
  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open,    setOpen]    = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const search = useCallback((q: string) => {
    if (!q.trim()) { setResults([]); setOpen(false); return }
    setLoading(true)
    api.search(q, 8).then((res: any) => {
      setResults(res.results)
      setOpen(true)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const onType = (q: string) => {
    setQuery(q)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => search(q), 300)
  }

  const pick = (r: SearchResult) => {
    onSelect(r.node_id)
    setQuery(r.name)
    setOpen(false)
  }

  const clear = () => {
    setQuery('')
    setResults([])
    setOpen(false)
    onSelect('')
  }

  return (
    <div style={{ position: 'relative', width: '280px' }}>
      <div style={{
        display:      'flex',
        alignItems:   'center',
        gap:          '6px',
        background:   '#0f172a',
        border:       '1px solid #1e293b',
        borderRadius: '6px',
        padding:      '6px 10px',
      }}>
        <Search size={13} color="#475569" />
        <input
          value={query}
          onChange={e => onType(e.target.value)}
          placeholder="Search nodes..."
          style={{
            background:  'none',
            border:      'none',
            outline:     'none',
            color:       '#e2e8f0',
            fontSize:    '12px',
            fontFamily:  'monospace',
            width:       '100%',
          }}
        />
        {loading && (
          <span style={{ color: '#475569', fontSize: '11px' }}>...</span>
        )}
        {query && !loading && (
          <button onClick={clear} style={{
            background: 'none', border: 'none',
            cursor: 'pointer', padding: '0',
          }}>
            <X size={12} color="#475569" />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div style={{
          position:     'absolute',
          top:          '36px',
          left:         0,
          right:        0,
          background:   '#0f172a',
          border:       '1px solid #1e293b',
          borderRadius: '6px',
          zIndex:       50,
          overflow:     'hidden',
          boxShadow:    '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          {results.map(r => (
            <div
              key={r.node_id}
              onClick={() => pick(r)}
              style={{
                display:     'flex',
                alignItems:  'center',
                gap:         '8px',
                padding:     '8px 12px',
                cursor:      'pointer',
                borderBottom:'1px solid #0f172a',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.background = '#1e293b'
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.background = 'transparent'
              }}
            >
              <div style={{
                width:        '7px',
                height:       '7px',
                borderRadius: '50%',
                background:   NODE_COLORS[r.type] ?? '#94a3b8',
                flexShrink:   0,
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color:        '#e2e8f0',
                  fontSize:     '12px',
                  fontFamily:   'monospace',
                  overflow:     'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace:   'nowrap',
                }}>
                  {r.name}
                </div>
                <div style={{
                  color:        '#475569',
                  fontSize:     '10px',
                  overflow:     'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace:   'nowrap',
                }}>
                  {r.file}
                </div>
              </div>
              <span style={{
                color:        '#334155',
                fontSize:     '10px',
                fontFamily:   'monospace',
                flexShrink:   0,
              }}>
                {(r.score * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
