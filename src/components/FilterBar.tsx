'use client'
import { NODE_COLORS } from '@/types/graph'

const TYPES = ['function', 'method', 'class', 'module'] as const

interface Props {
  activeTypes: Set<string>
  onToggle: (type: string) => void
  stats: { nodes: number; edges: number } | null
}

export default function FilterBar({ activeTypes, onToggle, stats }: Props) {
  return (
    <div style={{
      display:    'flex',
      alignItems: 'center',
      gap:        '6px',
    }}>
      {TYPES.map(t => {
        const active = activeTypes.has(t)
        const color  = NODE_COLORS[t]
        return (
          <button
            key={t}
            onClick={() => onToggle(t)}
            style={{
              display:      'flex',
              alignItems:   'center',
              gap:          '5px',
              padding:      '4px 10px',
              background:   active ? color + '22' : 'transparent',
              border:       `1px solid ${active ? color + '66' : '#1e293b'}`,
              borderRadius: '5px',
              color:        active ? color : '#475569',
              fontSize:     '11px',
              fontFamily:   'monospace',
              cursor:       'pointer',
              transition:   'all 0.15s',
            }}
          >
            <div style={{
              width:        '6px',
              height:       '6px',
              borderRadius: t === 'class' ? '1px' : '50%',
              background:   active ? color : '#334155',
              flexShrink:   0,
            }} />
            {t}
          </button>
        )
      })}

      {stats && (
        <div style={{
          marginLeft: '8px',
          color:      '#334155',
          fontSize:   '11px',
          fontFamily: 'monospace',
        }}>
          {stats.nodes}n · {stats.edges}e
        </div>
      )}
    </div>
  )
}
