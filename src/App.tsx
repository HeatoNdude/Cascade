import { useState } from 'react'

const BACKEND = 'http://localhost:5001'

export default function App() {
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState('')
  const [backend, setBackend] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function sendPrompt() {
    if (!prompt.trim()) return
    setLoading(true)
    setResponse('')
    setError('')
    setBackend('')

    try {
      const res = await fetch(`${BACKEND}/prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setResponse(data.response)
      setBackend(data.backend_used)
    } catch (e: any) {
      setError(`Backend unreachable: ${e.message}. Is uvicorn running on port 5001?`)
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendPrompt()
  }

  return (
    <main style={{
      padding: '2rem',
      fontFamily: 'monospace',
      maxWidth: '720px',
      margin: '0 auto'
    }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '22px', fontWeight: 500, margin: 0 }}>
          Cascade
        </h1>
        <p style={{ fontSize: '12px', color: '#888', margin: '4px 0 0' }}>
          Codebase simulation engine · Phase 1 Foundation
        </p>
      </div>

      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        onKeyDown={handleKey}
        placeholder="Type a prompt... (Ctrl+Enter to send)"
        rows={5}
        style={{
          width: '100%',
          padding: '10px',
          fontSize: '13px',
          fontFamily: 'monospace',
          border: '1px solid #ddd',
          borderRadius: '6px',
          resize: 'vertical',
          marginBottom: '8px',
          boxSizing: 'border-box'
        }}
      />

      <button
        onClick={sendPrompt}
        disabled={loading || !prompt.trim()}
        style={{
          padding: '8px 20px',
          fontSize: '13px',
          cursor: loading ? 'wait' : 'pointer',
          borderRadius: '5px',
          border: '1px solid #ccc',
          background: loading ? '#f0f0f0' : '#fff',
          fontFamily: 'monospace'
        }}
      >
        {loading ? 'Thinking...' : 'Send →'}
      </button>

      {error && (
        <div style={{
          marginTop: '1rem',
          padding: '10px 14px',
          background: '#fff5f5',
          border: '1px solid #fcc',
          borderRadius: '6px',
          fontSize: '12px',
          color: '#c00'
        }}>
          {error}
        </div>
      )}

      {response && (
        <div style={{
          marginTop: '1.5rem',
          padding: '14px 16px',
          background: '#f9f9f9',
          border: '1px solid #e8e8e8',
          borderRadius: '6px'
        }}>
          <div style={{
            fontSize: '10px',
            color: '#999',
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.06em'
          }}>
            via {backend}
          </div>
          <div style={{
            fontSize: '13px',
            lineHeight: 1.75,
            color: '#222',
            whiteSpace: 'pre-wrap'
          }}>
            {response}
          </div>
        </div>
      )}
    </main>
  )
}
