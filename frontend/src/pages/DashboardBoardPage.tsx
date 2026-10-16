import { useParams, Link } from 'react-router-dom'
import { useSecuredUrl } from '../components/chat/helpers'
import { ArrowLeftIcon, BarChartIcon } from '../components/icons'

/* ============================================================
   分析看板轻量页：整页展示 registry 组装的自包含看板 HTML
   （KPI 卡 + 图表内联 + plotly 内联）。iframe 走 5 秒 sse
   token（S1.2 不落长期 JWT）+ sandbox 沙箱。
   ============================================================ */

export default function DashboardBoardPage() {
  const { key } = useParams<{ key: string }>()
  const src = useSecuredUrl(key ? `/api/v1/data/dashboard-html/${key}` : '')

  if (!key) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>
        看板参数缺失
        <div style={{ marginTop: 16 }}>
          <Link to="/chat" style={{ color: 'var(--accent)', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 4, lineHeight: 1 }}><ArrowLeftIcon size={13} /> 返回对话</Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px',
        borderBottom: '1px solid var(--border)', background: 'var(--bg-primary)',
      }}>
        <Link to="/chat" style={{ color: 'var(--text-secondary)', display: 'inline-flex', lineHeight: 1 }}
          aria-label="返回对话"><ArrowLeftIcon size={16} /></Link>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
          <BarChartIcon size={15} /> 分析看板
        </span>
      </div>
      <iframe
        src={src}
        sandbox="allow-scripts"
        title="分析看板"
        style={{ flex: 1, width: '100%', border: 0, background: '#f5f6f8' }}
      />
    </div>
  )
}
