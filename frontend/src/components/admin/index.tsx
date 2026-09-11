import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './shared'
import DashboardTab from './DashboardTab'
import UsersTab from './UsersTab'
import AgentsTab from './AgentsTab'
import AgentDevicesTab from './AgentDevicesTab'
import SessionsTab from './SessionsTab'
import ModelsTab from './ModelsTab'
import WebsitesTab from './WebsitesTab'
import DatasetsTab from './DatasetsTab'
import KnowledgeTab from './KnowledgeTab'
import FilesTab from './FilesTab'
import ToolsTab from './ToolsTab'
import SettingsTab from './SettingsTab'
import MonitorTab from './MonitorTab'

// 后台导航：左侧边栏按维度分组（桌面），移动端回退横向滚动 chip
const NAV_GROUPS: { label: string; icon: string; items: { key: string; label: string }[] }[] = [
  { label: '概览', icon: '📊', items: [{ key: 'dashboard', label: '仪表盘' }] },
  {
    label: '用户维度', icon: '👥',
    items: [
      { key: 'users', label: '用户管理' },
      { key: 'sessions', label: '会话记录' },
    ],
  },
  {
    label: 'Agent 维度', icon: '🤖',
    items: [
      { key: 'agents', label: 'Agent 状态' },
      { key: 'agent-devices', label: 'Agent 管理' },
      { key: 'tools', label: '工具' },
    ],
  },
  {
    label: '数据维度', icon: '📦',
    items: [
      { key: 'datasets', label: '数据集' },
      { key: 'knowledge', label: '知识库' },
      { key: 'websites', label: '网站管理' },
      { key: 'files', label: '文件管理' },
    ],
  },
  {
    label: '系统维度', icon: '⚙️',
    items: [
      { key: 'models', label: '模型配置' },
      { key: 'monitor', label: '代码监控' },
      { key: 'settings', label: '设置' },
    ],
  },
]

function AdminPageInner({ isAdmin }: { isAdmin: boolean }) {
  const navigate = useNavigate()
  const location = useLocation()
  // Extract current tab from URL path: /admin/dashboard → dashboard
  const currentTab = location.pathname.split('/').pop() || 'dashboard'

  const itemBtnStyle = (active: boolean): React.CSSProperties => ({
    width: '100%', textAlign: 'left', padding: '9px 12px', borderRadius: 8, border: 'none',
    // 激活项实心 accent + 白字，层级最重；非激活透明底浅色字
    background: active ? 'var(--accent)' : 'transparent',
    color: active ? '#fff' : 'var(--text-secondary)',
    fontWeight: active ? 600 : 400, fontSize: 13, cursor: 'pointer',
    whiteSpace: 'nowrap', marginBottom: 2,
    transition: 'background 0.15s, color 0.15s',
  })

  // 桌面侧边栏：卡片容器 + 分组标题（emoji + 加粗）+ 组间分隔线
  const sidebar = (
    <nav style={{
      width: 200, flexShrink: 0, overflowY: 'auto', alignSelf: 'flex-start',
      background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 12,
      padding: '12px 8px', maxHeight: '100%',
    }}>
      {NAV_GROUPS.map((g, gi) => (
        <div key={g.label} style={{
          paddingTop: gi > 0 ? 12 : 0,
          borderTop: gi > 0 ? '1px solid var(--border-light)' : 'none',
          marginBottom: gi === NAV_GROUPS.length - 1 ? 0 : 6,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px 8px', fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
            <span style={{ fontSize: 14 }}>{g.icon}</span>
            {g.label}
          </div>
          {g.items.map((t) => (
            <button key={t.key} onClick={() => navigate(`/chat/admin/${t.key}`)}
              style={itemBtnStyle(currentTab === t.key)}
              onMouseEnter={(e) => { if (currentTab !== t.key) e.currentTarget.style.background = 'var(--hover-bg)' }}
              onMouseLeave={(e) => { if (currentTab !== t.key) e.currentTarget.style.background = 'transparent' }}
            >{t.label}</button>
          ))}
        </div>
      ))}
    </nav>
  )

  // 移动端横向滚动 chip（分组信息放 title，chip 文本带分组 emoji 前缀）
  const mobileChips = (
    <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 4 }}>
      {NAV_GROUPS.flatMap((g) => g.items).map((t) => {
        const group = NAV_GROUPS.find((g) => g.items.some((i) => i.key === t.key))
        return (
          <button key={t.key} onClick={() => navigate(`/chat/admin/${t.key}`)}
            title={`${group?.label} · ${t.label}`}
            style={{
              ...itemBtnStyle(currentTab === t.key),
              width: 'auto', padding: '7px 14px', borderRadius: 16,
              border: currentTab === t.key ? '1px solid var(--accent)' : '1px solid var(--border)',
              flexShrink: 0,
            }}>{group?.icon} {t.label}</button>
        )
      })}
    </div>
  )

  return (
    <div className="admin-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 12px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: 'var(--bg-secondary)' }}>
      <style>{`
        @media (min-width: 769px) {
          .admin-page { padding: 24px 28px !important; gap: 20px !important; }
          .admin-mobile-nav { display: none !important; }
        }
        @media (max-width: 768px) {
          .admin-sidebar { display: none !important; }
          .admin-layout { flex-direction: column !important; }
        }
        @media (max-width: 480px) {
          .admin-page { padding: 12px 8px !important; gap: 12px !important; }
        }
      `}</style>
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>后台管理</h2>
      <div className="admin-mobile-nav">{mobileChips}</div>
      <div className="admin-layout" style={{ flex: 1, display: 'flex', gap: 20, minHeight: 0 }}>
        <div className="admin-sidebar">{sidebar}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Routes>
            <Route path="/" element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardTab isAdmin={isAdmin} />} />
            <Route path="users" element={<UsersTab />} />
            <Route path="agents" element={<AgentsTab />} />
            <Route path="agent-devices" element={<AgentDevicesTab />} />
            <Route path="sessions" element={<SessionsTab />} />
            <Route path="models" element={<ModelsTab />} />
            <Route path="websites" element={<WebsitesTab />} />
            <Route path="datasets" element={<DatasetsTab />} />
            <Route path="knowledge" element={<KnowledgeTab />} />
            <Route path="files" element={<FilesTab />} />
            <Route path="tools" element={<ToolsTab />} />
            <Route path="monitor" element={<MonitorTab />} />
            <Route path="settings" element={<SettingsTab />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}

export default function AdminPage({ isAdmin }: { isAdmin: boolean }) {
  return <ErrorBoundary><AdminPageInner isAdmin={isAdmin} /></ErrorBoundary>
}
