import { Component, useState, useEffect } from 'react'
import ChatPage from './components/ChatPage'
import LoginPage from './components/LoginPage'
import AdminPage from './components/AdminPage'
import UserPage from './components/UserPage'
import AgentPage from './components/AgentPage'
import AgentStatus from './components/AgentStatus'
import { checkToken, setStoredUser } from './api'

class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: string }> {
  state = { hasError: false, error: '' }
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e.message } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <h3 style={{ color: '#e53935' }}>页面异常</h3>
          <p style={{ fontSize: 13, color: '#999', margin: '8px 0' }}>{this.state.error}</p>
          <button onClick={() => window.location.reload()} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer', border: '1px solid #ddd', borderRadius: 6, background: '#fff', fontSize: 13 }}>刷新页面</button>
        </div>
      )
    }
    return this.props.children
  }
}

type Page = 'chat' | 'user' | 'agent' | 'admin'

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState<Page>('chat')
  const [chatFocus, setChatFocus] = useState(0)

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
    if (!newToken) return
    localStorage.setItem('token', newToken)
    setStoredUser(newUser)
    setUser(newUser)
    setToken(newToken)
    setPage('chat')
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
          <button onClick={() => { setPage('chat'); setChatFocus(c => c + 1) }} style={tabStyle('chat')}>对话</button>
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
        <ErrorBoundary>
          {page === 'chat' && <ChatPage user={user} focusKey={chatFocus} />}
          {page === 'user' && <UserPage user={user} onLogout={handleLogout} />}
          {page === 'agent' && <AgentPage userId={user?.id} />}
          {page === 'admin' && isAdmin && <AdminPage isAdmin={isAdmin} />}
        </ErrorBoundary>
      </main>
    </div>
  )
}

export default App
