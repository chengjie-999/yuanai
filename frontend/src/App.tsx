import { useState, useEffect } from 'react'
import ChatPage from './components/ChatPage'
import ToolsPage from './components/ToolsPage'
import LoginPage from './components/LoginPage'
import SettingsPage, { useFeatureToggles } from './components/SettingsPage'
import DataAnalysisPage from './components/DataAnalysisPage'
import AdminPage from './components/AdminPage'
import DataCollectionPage from './components/DataCollectionPage'
import DatasetPage from './components/DatasetPage'
import { checkToken, setStoredUser } from './api'

type Page = 'chat' | 'datasets' | 'dataCollection' | 'tools' | 'dataAnalysis' | 'admin' | 'settings'

const BASE_TABS: { key: Page; label: string; icon: string }[] = [
  { key: 'chat', label: '聊天', icon: '💬' },
]

const FEATURE_TABS: { key: Page; label: string; icon: string; toggleKey: string; adminOnly?: boolean }[] = [
  { key: 'datasets', label: '数据工作台', icon: '📂', toggleKey: 'datasets' },
  { key: 'dataAnalysis', label: '数据分析', icon: '📊', toggleKey: 'dataAnalysis' },
  { key: 'dataCollection', label: '数据采集', icon: '📡', toggleKey: 'dataCollection', adminOnly: true },
  { key: 'tools', label: '工具', icon: '🔧', toggleKey: 'tools' },
]

function App() {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState<Page>('chat')
  const [toggles, toggleFeature] = useFeatureToggles()

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

  const tabs: { key: Page; label: string; icon: string }[] = [
    ...BASE_TABS,
    ...FEATURE_TABS.filter((t) => toggles[t.toggleKey] && (!t.adminOnly || isAdmin)).map(({ key, label, icon }) => ({ key, label, icon })),
  ]

  const showSettings = page === 'settings'

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        background: '#fff', borderBottom: '1px solid #e5e5e5',
        padding: '0 20px', display: 'flex', alignItems: 'center', height: 52, flexShrink: 0,
      }}>
        <span style={{ fontSize: 17, fontWeight: 700, color: '#333', marginRight: 32, letterSpacing: -0.3 }}>
          小元AI
        </span>
        <nav style={{ display: 'flex', gap: 2, overflow: 'hidden' }}>
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setPage(t.key)}
              style={{
                background: 'transparent', border: 'none',
                color: page === t.key ? '#333' : '#999',
                fontWeight: page === t.key ? 600 : 400, fontSize: 14,
                padding: '0 14px', height: 52, cursor: 'pointer',
                borderBottom: page === t.key ? '2px solid #333' : '2px solid transparent',
                transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap',
              }}
            >
              <span style={{ fontSize: 15 }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: '#999' }}>{user?.username || user?.display_name}</span>
          <button onClick={handleLogout} style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 13, padding: 0 }}>退出</button>
          {isAdmin && (
            <button onClick={() => setPage(page === 'admin' ? 'chat' : 'admin')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: page === 'admin' ? '#1976d2' : '#999', padding: '4px', lineHeight: 1 }}>👤</button>
          )}
          <button onClick={() => setPage(showSettings ? 'chat' : 'settings')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: showSettings ? '#1976d2' : '#999', padding: '4px', lineHeight: 1 }}>⚙</button>
        </div>
      </header>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        {page === 'chat' && <ChatPage user={user} />}
        {page === 'datasets' && toggles.datasets && <DatasetPage />}
        {page === 'dataCollection' && toggles.dataCollection && isAdmin && <DataCollectionPage />}
        {page === 'tools' && toggles.tools && <ToolsPage />}
        {page === 'dataAnalysis' && toggles.dataAnalysis && <DataAnalysisPage />}
        {page === 'admin' && isAdmin && <AdminPage />}
        {page === 'settings' && <SettingsPage toggles={toggles} onToggle={toggleFeature} />}
      </main>
    </div>
  )
}

export default App
