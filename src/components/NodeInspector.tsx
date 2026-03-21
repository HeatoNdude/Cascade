'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { NODE_COLORS } from '@/types/graph'
import type { NodeDetail } from '@/types/graph'
import { X, GitCommit, User, FileCode } from 'lucide-react'

interface Props {
  nodeId: string | null
  onClose: () => void
}

export default function NodeInspector({ nodeId, onClose }: Props) {
  const [detail, setDetail] = useState<{
    id: string
    data: NodeDetail
    callers: string[]
    callees: string[]
  } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!nodeId) { setDetail(null); return }
    setLoading(true)
    api.node(nodeId)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [nodeId])

  if (!nodeId) return null

  const color = detail ? NODE_COLORS[detail.data.type] ?? '#94a3b8' : '#94a3b8'

  return (
    <div style={{
      position:      'absolute',
      top:           0,
      right:         0,
      width:         '320px',
      height:        '100%',
      background:    '#0f172a',
      borderLeft:    '1px solid #1e293b',
      display:       'flex',
      flexDirection: 'column',
      zIndex:        20,
      fontFamily:    'monospace',
      fontSize:      '12px',
      color:         '#cbd5e1',
      overflowY:     'auto',
    }}>
      {/* Header */}
      <div style={{
        display:        'flex',
        alignItems:     'center',
        justifyContent: 'space-between',
        padding:        '12px 14px',
        borderBottom:   '1px solid #1e293b',
        flexShrink:     0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width:        '10px',
            height:       '10px',
            borderRadius: '50%',
            background:   color,
            flexShrink:   0,
          }} />
          <span style={{ color: '#f1f5f9', fontWeight: 500, fontSize: '13px' }}>
            {loading ? 'Loading...' : (detail?.data.label ?? nodeId)}
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border:     'none',
            cursor:     'pointer',
            color:      '#64748b',
            padding:    '2px',
          }}
        >
          <X size={14} />
        </button>
      </div>

      {loading && (
        <div style={{ padding: '16px', color: '#64748b' }}>Loading node data...</div>
      )}

      {detail && !loading && (
        <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Type + language */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{
              background:   color + '22',
              color:        color,
              border:       `1px solid ${color}44`,
              borderRadius: '4px',
              padding:      '2px 8px',
              fontSize:     '11px',
            }}>
              {detail.data.type}
            </span>
            <span style={{
              background:   '#1e293b',
              color:        '#94a3b8',
              borderRadius: '4px',
              padding:      '2px 8px',
              fontSize:     '11px',
            }}>
              {detail.data.language}
            </span>
            {detail.data.is_async && (
              <span style={{
                background:   '#064e3b',
                color:        '#6ee7b7',
                borderRadius: '4px',
                padding:      '2px 8px',
                fontSize:     '11px',
              }}>
                async
              </span>
            )}
          </div>

          {/* File location */}
          <div>
            <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '4px' }}>
              <FileCode size={11} style={{ display: 'inline', marginRight: '4px' }} />
              FILE
            </div>
            <div style={{ color: '#94a3b8', wordBreak: 'break-all' }}>
              {detail.data.file}
              {detail.data.line_start && (
                <span style={{ color: '#475569' }}>
                  :{detail.data.line_start}–{detail.data.line_end}
                </span>
              )}
            </div>
          </div>

          {/* Docstring */}
          {detail.data.docstring && (
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '4px' }}>
                DOCSTRING
              </div>
              <div style={{
                background:   '#1e293b',
                borderRadius: '4px',
                padding:      '8px',
                color:        '#94a3b8',
                lineHeight:   1.55,
                fontSize:     '11.5px',
              }}>
                {detail.data.docstring}
              </div>
            </div>
          )}

          {/* Params */}
          {detail.data.params && detail.data.params.length > 0 && (
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '4px' }}>
                PARAMS
              </div>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {detail.data.params.map((p: string) => (
                  <span key={p} style={{
                    background:   '#1e293b',
                    color:        '#7dd3fc',
                    borderRadius: '3px',
                    padding:      '1px 6px',
                    fontSize:     '11px',
                  }}>
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Git blame */}
          <div>
            <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '6px' }}>
              <User size={11} style={{ display: 'inline', marginRight: '4px' }} />
              GIT
            </div>
            {detail.data.primary_author && (
              <div style={{ marginBottom: '4px' }}>
                <span style={{ color: '#475569' }}>author  </span>
                <span style={{ color: '#94a3b8' }}>{detail.data.primary_author}</span>
              </div>
            )}
            {detail.data.last_modified && (
              <div style={{ marginBottom: '4px' }}>
                <span style={{ color: '#475569' }}>modified </span>
                <span style={{ color: '#94a3b8' }}>
                  {detail.data.last_modified.slice(0, 10)}
                </span>
              </div>
            )}
            {detail.data.last_commit && (
              <div style={{
                background:   '#1e293b',
                borderRadius: '4px',
                padding:      '6px 8px',
                color:        '#64748b',
                marginTop:    '4px',
                lineHeight:   1.5,
              }}>
                {detail.data.last_commit.slice(0, 120)}
              </div>
            )}
          </div>

          {/* Commit history */}
          {detail.data.history && detail.data.history.length > 0 && (
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '6px' }}>
                <GitCommit size={11} style={{ display: 'inline', marginRight: '4px' }} />
                HISTORY
              </div>
              {detail.data.history.slice(0, 4).map((h: any, i: number) => (
                <div key={i} style={{
                  borderLeft:   '2px solid #1e293b',
                  paddingLeft:  '8px',
                  marginBottom: '8px',
                }}>
                  <div style={{ display: 'flex', gap: '6px', marginBottom: '2px' }}>
                    <span style={{ color: '#475569' }}>{h.hash}</span>
                    <span style={{ color: '#475569' }}>{h.date.slice(0, 10)}</span>
                  </div>
                  <div style={{ color: '#94a3b8', lineHeight: 1.4 }}>
                    {h.message.slice(0, 100)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Callers */}
          {detail.callers.length > 0 && (
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '6px' }}>
                CALLED BY ({detail.callers.length})
              </div>
              {detail.callers.slice(0, 6).map((c: string) => (
                <div key={c} style={{
                  color:        '#94a3b8',
                  padding:      '3px 0',
                  borderBottom: '1px solid #0f172a',
                  fontSize:     '11px',
                  overflow:     'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace:   'nowrap',
                }}>
                  {c.split('::')[1] ?? c}
                </div>
              ))}
            </div>
          )}

          {/* Callees */}
          {detail.callees.length > 0 && (
            <div>
              <div style={{ color: '#64748b', fontSize: '11px', marginBottom: '6px' }}>
                CALLS ({detail.callees.length})
              </div>
              {detail.callees.slice(0, 6).map((c: string) => (
                <div key={c} style={{
                  color:        '#94a3b8',
                  padding:      '3px 0',
                  borderBottom: '1px solid #0f172a',
                  fontSize:     '11px',
                  overflow:     'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace:   'nowrap',
                }}>
                  {c.split('::')[1] ?? c}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
