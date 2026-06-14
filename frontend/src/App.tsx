import { useEffect, useState } from 'react'

type HealthStatus = 'checking...' | 'Backend connected ✓' | 'Backend unreachable'

function App() {
  const [health, setHealth] = useState<HealthStatus>('checking...')

  useEffect(() => {
    fetch('/api/health/live')
      .then((r) => r.json())
      .then((data) =>
        setHealth(data.status === 'ok' ? 'Backend connected ✓' : 'Backend unreachable'),
      )
      .catch(() => setHealth('Backend unreachable'))
  }, [])

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>AI 学习导师</h1>
      <p>Backend: {health}</p>
    </div>
  )
}

export default App
