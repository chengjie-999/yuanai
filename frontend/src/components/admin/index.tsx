import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { ErrorBoundary } from './shared'
import DashboardTab from './DashboardTab'
import UsersTab from './UsersTab'
import UserAnalyticsTab from './UserAnalyticsTab'
import { ChatAnalyticsTab, FeatureAnalyticsTab, RetentionAnalyticsTab, CostAnalyticsTab } from './AnalyticsTabs'
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

// 分组图标：内联 SVG stroke（lucide 风格，项目零图标库），随文字颜色
const GIcon = ({ d }: { d: React.ReactNode }) => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">{d}</svg>
)

// 后台导航：左侧边栏按维度分组（桌面），移动端回退横向滚动 chip
const NAV_GROUPS: { label: string; icon: React.ReactNode; items: { key: string; label: string }[] }[] = [
  {
    label: '概览',
    icon: <GIcon d={<><rect width="7" height="9" x="3" y="3" rx="1" /><rect width="7" height="5" x="14" y="3" rx="1" /><rect width="7" height="9" x="14" y="12" rx="1" /><rect width="7" height="5" x="3" y="16" rx="1" /></>} />,
    items: [{ key: 'dashboard', label: '仪表盘' }],
  },
  {
    label: '用户维度',
    icon: <GIcon d={<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></>} />,
    items: [
      { key: 'users', label: '用户管理' },
      { key: 'sessions', label: '会话记录' },
    ],
  },
  {
    label: '数据分析',
    icon: <GIcon d={<><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></>} />,
    items: [
      { key: 'user-analytics', label: '用户分析' },
      { key: 'chat-analytics', label: '对话分析' },
      { key: 'feature-analytics', label: '功能分析' },
      { key: 'retention-analytics', label: '留存分析' },
      { key: 'cost-analytics', label: '成本分析' },
    ],
  },
  {
    label: 'Agent 维度',
    icon: <GIcon d={<><path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="M2 14h2" /><path d="M20 14h2" /><path d="M15 13v2" /><path d="M9 13v2" /></>} />,
    items: [
      { key: 'agents', label: 'Agent 状态' },
      { key: 'agent-devices', label: 'Agent 管理' },
      { key: 'tools', label: '工具' },
    ],
  },
  {
    label: '数据维度',
    icon: <GIcon d={<><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5V19A9 3 0 0 0 21 19V5" /><path d="M3 12A9 3 0 0 0 21 12" /></>} />,
    items: [
      { key: 'datasets', label: '数据集' },
      { key: 'knowledge', label: '知识库' },
      { key: 'websites', label: '网站管理' },
      { key: 'files', label: '文件管理' },
    ],
  },
  {
    label: '系统维度',
    icon: <GIcon d={<><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></>} />,
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
    width: '100%', textAlign: 'left', padding: '9px 12px 9px 30px', borderRadius: 8, border: 'none',
    // 二级项相对分组标题右移缩进，层级区分；激活项实心 accent + 白字最重
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 12px 8px', fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)' }}>
            <span style={{ display: 'flex', alignItems: 'center' }}>{g.icon}</span>
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
            }}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>{group?.icon} {t.label}</span></button>
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
            <Route path="user-analytics" element={<UserAnalyticsTab />} />
            <Route path="chat-analytics" element={<ChatAnalyticsTab />} />
            <Route path="feature-analytics" element={<FeatureAnalyticsTab />} />
            <Route path="retention-analytics" element={<RetentionAnalyticsTab />} />
            <Route path="cost-analytics" element={<CostAnalyticsTab />} />
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
