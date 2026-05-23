import { useState, useEffect } from 'react'
import ChatPage from './components/ChatPage'
import LoginPage from './components/LoginPage'
import AdminPage from './components/AdminPage'
import UserPage from './components/UserPage'
import AgentPage from './components/AgentPage'
import AgentStatus from './components/AgentStatus'
import { checkToken, setStoredUser } from './api'

type Page = 'chat' | 'user' | 'agent' | 'admin'

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

  const tabStyle = (key: Page) => ({
    background: 'transparent', border: 'none',
    color: page === key ? '#333' : '#999',
    fontWeight: (page === key ? 600 : 400) as any, fontSize: 14,
    padding: '0 14px', height: 52, cursor: 'pointer',
    borderBottom: page === key ? '2px solid #333' : '2px solid transparent',
    transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
  })

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
          <button onClick={() => setPage('chat')} style={tabStyle('chat')}>对话</button>
          {isAdmin && (
            <button onClick={() => setPage('admin')} style={tabStyle('admin')}>后台管理</button>
          )}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span onClick={() => setPage('agent')} style={{ cursor: 'pointer' }}>
            <AgentStatus userId={user?.id} />
          </span>
          <span onClick={() => setPage('user')} style={{
            fontSize: 13, color: '#1976d2', cursor: 'pointer',
            borderBottom: page === 'user' ? '1px solid #1976d2' : '1px solid transparent',
          }}>{user?.username || user?.display_name}</span>
        </div>
      </header>
      <main style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {page === 'chat' && <ChatPage user={user} />}
        {page === 'user' && <UserPage user={user} onLogout={handleLogout} />}
        {page === 'agent' && <AgentPage userId={user?.id} />}
        {page === 'admin' && isAdmin && <AdminPage isAdmin={isAdmin} />}
      </main>
    </div>
  )
}

export default App
