'use client'
import { useState } from 'react'
import { FolderOpen, Zap } from 'lucide-react'

interface Props {
  onOpen: (path: string) => void
  isBuilding: boolean
  progress: { current: number; total: number; current_file: string }
}

export default function RepoPicker({ onOpen, isBuilding, progress }: Props) {
  const [path, setPath] = useState('')

  const submit = () => {
    if (path.trim()) onOpen(path.trim())
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') submit()
  }

  const pct = progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      alignItems:     'center',
      justifyContent: 'center',
      height:         '100%',
      background:     '#080f1a',
      fontFamily:     'monospace',
    }}>
      <div style={{
        width:        '480px',
        background:   '#0f172a',
        border:       '1px solid #1e293b',
        borderRadius: '10px',
        padding:      '32px',
      }}>
        <div style={{
          display:     'flex',
          alignItems:  'center',
          gap:         '10px',
          marginBottom:'24px',
        }}>
          <Zap size={20} color="#3b82f6" />
          <span style={{ color: '#f1f5f9', fontSize: '18px', fontWeight: 500 }}>
            Cascade
          </span>
          <span style={{ color: '#334155', fontSize: '12px' }}>
            God View · v0.2
          </span>
        </div>

        <div style={{ color: '#64748b', fontSize: '12px', marginBottom: '16px' }}>
          Open a repository to build the entity graph
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input
            value={path}
            onChange={e => setPath(e.target.value)}
            onKeyDown={handleKey}
            placeholder="D:\my-project or /home/user/project"
            disabled={isBuilding}
            style={{
              flex:         1,
              background:   '#0a1628',
              border:       '1px solid #1e293b',
              borderRadius: '6px',
              padding:      '9px 12px',
              color:        '#e2e8f0',
              fontSize:     '12px',
              fontFamily:   'monospace',
              outline:      'none',
            }}
          />
          <button
            onClick={submit}
            disabled={isBuilding || !path.trim()}
            style={{
              display:        'flex',
              alignItems:     'center',
              gap:            '6px',
              padding:        '9px 16px',
              background:     isBuilding ? '#1e293b' : '#1d4ed8',
              border:         'none',
              borderRadius:   '6px',
              color:          isBuilding ? '#475569' : '#fff',
              fontSize:       '12px',
              fontFamily:     'monospace',
              cursor:         isBuilding ? 'wait' : 'pointer',
            }}
          >
            <FolderOpen size={13} />
            {isBuilding ? 'Building…' : 'Open'}
          </button>
        </div>

        {/* Recent paths shortcut */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {['D:\\cascade\\cascade\\backend', 'D:\\cascade\\cascade'].map(p => (
            <button
              key={p}
              onClick={() => { setPath(p); onOpen(p) }}
              disabled={isBuilding}
              style={{
                background:   '#0a1628',
                border:       '1px solid #1e293b',
                borderRadius: '4px',
                padding:      '3px 8px',
                color:        '#475569',
                fontSize:     '10px',
                fontFamily:   'monospace',
                cursor:       'pointer',
              }}
            >
              {p.split('\\').slice(-2).join('\\')}
            </button>
          ))}
        </div>

        {/* Build progress */}
        {isBuilding && (
          <div style={{ marginTop: '20px' }}>
            <div style={{
              display:        'flex',
              justifyContent: 'space-between',
              marginBottom:   '6px',
              color:          '#64748b',
              fontSize:       '11px',
            }}>
              <span>Indexing repository…</span>
              <span>{pct}%</span>
            </div>
            <div style={{
              background:   '#0a1628',
              borderRadius: '3px',
              height:       '3px',
              overflow:     'hidden',
            }}>
              <div style={{
                width:      `${pct}%`,
                height:     '100%',
                background: '#3b82f6',
                transition: 'width 0.3s ease',
              }} />
            </div>
            <div style={{
              color:        '#334155',
              fontSize:     '10px',
              marginTop:    '6px',
              overflow:     'hidden',
              textOverflow: 'ellipsis',
              whiteSpace:   'nowrap',
            }}>
              {progress.current_file
                ? progress.current_file.split('\\').pop()
                : 'Starting…'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
