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

const TABS = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'users', label: '用户管理' },
  { key: 'agents', label: 'Agent 状态' },
  { key: 'agent-devices', label: 'Agent 管理' },
  { key: 'sessions', label: '会话记录' },
  { key: 'models', label: '模型配置' },
  { key: 'websites', label: '网站管理' },
  { key: 'datasets', label: '数据集' },
  { key: 'knowledge', label: '知识库' },
  { key: 'files', label: '文件管理' },
  { key: 'tools', label: '工具' },
  { key: 'monitor', label: '代码监控' },
  { key: 'settings', label: '设置' },
]

function AdminPageInner({ isAdmin }: { isAdmin: boolean }) {
  const navigate = useNavigate()
  const location = useLocation()
  // Extract current tab from URL path: /admin/dashboard → dashboard
  const currentTab = location.pathname.split('/').pop() || 'dashboard'

  return (
    <div className="admin-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 12px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: 'var(--bg-secondary)' }}>
      <style>{`
        @media (min-width: 769px) {
          .admin-page { padding: 24px 28px !important; gap: 20px !important; }
        }
        @media (max-width: 480px) {
          .admin-page { padding: 12px 8px !important; gap: 12px !important; }
        }
      `}</style>
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>后台管理</h2>
      <div className="admin-tab-bar" style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', paddingBottom: 0, flexWrap: 'nowrap' }}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => navigate(`/chat/admin/${t.key}`)} style={{
            padding: '9px 16px', borderRadius: '8px 8px 0 0', border: 'none',
            background: currentTab === t.key ? 'var(--bg-primary)' : 'transparent',
            color: currentTab === t.key ? 'var(--accent)' : 'var(--text-secondary)',
            fontWeight: currentTab === t.key ? 600 : 400, fontSize: 13, cursor: 'pointer',
            borderBottom: currentTab === t.key ? '2px solid var(--accent)' : '2px solid transparent',
            whiteSpace: 'nowrap', transition: 'color 0.15s, border-color 0.15s',
          }}>{t.label}</button>
        ))}
      </div>
      <div style={{ flex: 1 }}>
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
  )
}

export default function AdminPage({ isAdmin }: { isAdmin: boolean }) {
  return <ErrorBoundary><AdminPageInner isAdmin={isAdmin} /></ErrorBoundary>
}
