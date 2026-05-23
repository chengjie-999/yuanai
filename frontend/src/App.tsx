import { useState, useEffect } from 'react'
import ChatPage from './components/ChatPage'
import LoginPage from './components/LoginPage'
import AdminPage from './components/AdminPage'
import AgentStatus from './components/AgentStatus'
import { checkToken, setStoredUser } from './api'

type Page = 'chat' | 'admin'

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState<Page>('chat')

  useEffect(() => {
    const saved = localStorage.getItem('token')
    if (saved) {
      checkToken().then((data) => {
        if (data.valid && data.user) {
          setToken(saved)
          setUser(data.user)
        } else {
          if (data.detail) sessionStorage.setItem('loginError', data.detail)
          localStorage.removeItem('token')
        }
        setLoading(false)
      })
    } else {
      setLoading(false)
    }
  }, [])

  const handleLogin = (newToken: string, newUser: any) => {
    localStorage.setItem('token', newToken)
    setToken(newToken)
    setUser(newUser)
    setStoredUser(newUser)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    setStoredUser(null)
    setToken(null)
    setUser(null)
  }

  if (loading) return null
  if (!token) return <LoginPage onLogin={handleLogin} />

  const isAdmin = user?.role === 'admin'

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#fff', borderBottom: '1px solid #e5e5e5',
        padding: '0 20px', display: 'flex', alignItems: 'center', height: 52, flexShrink: 0,
      }}>
        <span style={{ fontSize: 17, fontWeight: 700, color: '#333', marginRight: 32, letterSpacing: -0.3 }}>
          小元AI
        </span>
        <nav style={{ display: 'flex', gap: 2 }}>
          <button
            onClick={() => setPage('chat')}
            style={{
              background: 'transparent', border: 'none',
              color: page === 'chat' ? '#333' : '#999',
              fontWeight: page === 'chat' ? 600 : 400, fontSize: 14,
              padding: '0 14px', height: 52, cursor: 'pointer',
              borderBottom: page === 'chat' ? '2px solid #333' : '2px solid transparent',
              transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            对话
          </button>
          <button
            onClick={() => setPage('admin')}
            style={{
              background: 'transparent', border: 'none',
              color: page === 'admin' ? '#333' : '#999',
              fontWeight: page === 'admin' ? 600 : 400, fontSize: 14,
              padding: '0 14px', height: 52, cursor: 'pointer',
              borderBottom: page === 'admin' ? '2px solid #333' : '2px solid transparent',
              transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            后台管理
          </button>
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <AgentStatus userId={user?.id} />
          <span style={{ fontSize: 12, color: '#bbb', fontFamily: 'monospace' }}>ID:{user?.id}</span>
          <span style={{ fontSize: 13, color: '#999' }}>{user?.username || user?.display_name}</span>
          <button onClick={handleLogout} style={{
            background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 13, padding: 0,
          }}>退出</button>
        </div>
      </header>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        {page === 'chat' && <ChatPage user={user} />}
        {page === 'admin' && <AdminPage isAdmin={isAdmin} userId={user?.id} />}
      </main>
    </div>
  )
}

export default App
