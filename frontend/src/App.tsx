import { useState } from 'react'
import ChatPage from './components/ChatPage'
import ToolsPage from './components/ToolsPage'
import BrowserPage from './components/BrowserPage'
import MonitorPage from './components/MonitorPage'

type Page = 'chat' | 'browser' | 'tools' | 'monitor'

const tabs: { key: Page; label: string; icon: string }[] = [
  { key: 'chat', label: '聊天', icon: '💬' },
  { key: 'browser', label: '自动化', icon: '🕷' },
  { key: 'tools', label: '工具', icon: '🔧' },
  { key: 'monitor', label: '监控', icon: '📺' },
]

function App() {
  const [page, setPage] = useState<Page>('chat')

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
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setPage(t.key)}
              style={{
                background: 'transparent', border: 'none',
                color: page === t.key ? '#333' : '#999',
                fontWeight: page === t.key ? 600 : 400, fontSize: 14,
                padding: '0 16px', height: 52, cursor: 'pointer',
                borderBottom: page === t.key ? '2px solid #333' : '2px solid transparent',
                transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              <span style={{ fontSize: 15 }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main style={{ flex: 1, overflow: 'hidden' }}>
        {page === 'chat' && <ChatPage />}
        {page === 'browser' && <BrowserPage />}
        {page === 'tools' && <ToolsPage />}
        {page === 'monitor' && <MonitorPage />}
      </main>
    </div>
  )
}

export default App
