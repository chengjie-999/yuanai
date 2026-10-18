import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { API_BASE, getToken } from '../api'
import { useSecuredUrl } from '../components/chat/helpers'
import { ArrowLeftIcon, BarChartIcon } from '../components/icons'
import { renderBody } from '../components/analysis/ResultBlocks'

/* ============================================================
   通用分析大屏：任意分析脚本的 __RESULT__ JSON → 统一渲染
   - 渲染块（KPI 卡/段落/表格/分组 + KEY_LABELS）已抽到
     components/analysis/ResultBlocks.tsx（与计划页共用）
   - 主题跟随 CSS 变量；移动端自适应；数据过期时后端自动从历史恢复
   ============================================================ */

export default function AnalysisDashboard({ sessionId: propSid, onClose, hideBack }: {
  sessionId?: string; onClose?: () => void; hideBack?: boolean
} = {}) {
  const params = useParams<{ sessionId: string }>()
  const sessionId = propSid || params.sessionId
  const [data, setData] = useState<any>(null)
  const [meta, setMeta] = useState<{ recovered?: boolean; created_at?: string }>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // B1-10 分析历史：会话内历次分析结果，可回溯查看
  const [history, setHistory] = useState<any[]>([])
  const [viewingHist, setViewingHist] = useState<number | null>(null)

  const loadDashboard = () => {
    if (!sessionId) return
    // 数据优先 Redis 缓存；过期后后端自动从 analysis_history 恢复
    fetch(API_BASE + '/analysis/dashboard/' + sessionId, {
      headers: { Authorization: 'Bearer ' + getToken() },
    })
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 404 ? 'NOT_FOUND' : 'HTTP ' + r.status)
        return r.json()
      })
      .then((d) => {
        setMeta({ recovered: !!d.recovered, created_at: d.created_at })
        setData(d)
        setError('')
        setViewingHist(null)
      })
      .catch((e) => {
        setError(e.message === 'NOT_FOUND' ? '未找到大屏数据：请先在对话中完成一次分析' : '大屏加载失败，请稍后重试')
      })
      .finally(() => setLoading(false))
  }
  useEffect(() => { loadDashboard() }, [sessionId])  // eslint-disable-line react-hooks/exhaustive-deps

  // B1-10：拉取会话分析历史列表（JWT；后端已做会话归属校验）
  useEffect(() => {
    if (!sessionId) return
    fetch(API_BASE + '/analysis/history?session_id=' + sessionId, {
      headers: { Authorization: 'Bearer ' + getToken() },
    })
      .then((r) => (r.ok ? r.json() : { history: [] }))
      .then((d) => setHistory(Array.isArray(d.history) ? d.history : []))
      .catch(() => {})
  }, [sessionId])

  const viewEntry = (h: any) => {
    // 回溯查看历史分析结果（本地渲染，不发请求）
    setData(h.result && Object.keys(h.result).length ? h.result : null)
    setMeta({ recovered: false, created_at: h.create_time })
    setViewingHist(h.id)
    setError('')
  }

  // 图表 iframe 安全 URL（5 秒 sse token + 沙箱，S1.2）
  const chartSrc = useSecuredUrl(data?.chart_html || '')

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>加载中…</div>
  if (error) return (
    <div style={{ padding: 60, textAlign: 'center' }}>
      <div style={{ marginBottom: 12, opacity: 0.3, color: 'var(--text-muted)', display: 'flex', justifyContent: 'center' }}><BarChartIcon size={40} /></div>
      <div style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 16 }}>{error}</div>
      <Link to="/chat" style={{ color: 'var(--accent)', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 4, lineHeight: 1 }}><ArrowLeftIcon size={13} /> 返回对话</Link>
    </div>
  )
  if (!data) return null

  // 顶层：chart_html 单独 iframe；其余字段走通用渲染器
  const { chart_html, recovered, created_at, ...rest } = data
  const body = renderBody(rest)

  return (
    <div style={{ minHeight: '100dvh', background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column' }}>
      <header style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 14, background: 'var(--bg-primary)', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
        {hideBack ? null : onClose ? (
          <button onClick={onClose} style={{ color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1, padding: 0 }}><ArrowLeftIcon size={13} /> 返回对话</button>
        ) : (
          <Link to="/chat" style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1 }}><ArrowLeftIcon size={13} /> 返回</Link>
        )}
        <span style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>分析大屏</span>
        {created_at && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            数据时间 {created_at}{meta.recovered ? '（已从历史恢复）' : ''}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {viewingHist !== null && (
          <button onClick={loadDashboard} title="查看最新分析结果"
            style={{ fontSize: 11, padding: '4px 12px', borderRadius: 6, border: '1px solid var(--accent)', background: 'var(--accent-light)', color: 'var(--accent)', cursor: 'pointer' }}>
            回到最新
          </button>
        )}
        <button
          onClick={() => { navigator.clipboard.writeText(window.location.href).catch(() => {}) }}
          title="复制大屏链接"
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          复制链接
        </button>
      </header>

      <div style={{ flex: 1, padding: '16px 20px 40px', maxWidth: 1080, width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>
        {chart_html && (
          <div style={{ height: '60vh', minHeight: 380, marginBottom: 18, background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            <iframe src={chartSrc} sandbox="allow-scripts" style={{ width: '100%', height: '100%', border: 'none' }} title="交互图表" />
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>{body}</div>

        {/* B1-10 分析历史：会话内历次分析，点击回溯查看 */}
        {history.length > 0 && (
          <div style={{ marginTop: 28, borderTop: '1px solid var(--border-light)', paddingTop: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
              历史分析{viewingHist !== null ? '（查看中：已选中一条历史结果）' : '（最新在前）'}
            </div>
            {history.map((h: any) => (
              <button
                key={h.id}
                onClick={() => viewEntry(h)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                  padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-light)',
                  background: viewingHist === h.id ? 'var(--accent-light)' : 'var(--bg-primary)',
                  cursor: 'pointer', marginBottom: 6, fontSize: 12,
                  color: 'var(--text-primary)', textAlign: 'left',
                }}
              >
                <span style={{ fontWeight: 600, minWidth: 90, color: viewingHist === h.id ? 'var(--accent)' : 'var(--text-secondary)' }}>
                  {h.script_name || '分析'}
                </span>
                <span style={{ color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 11 }}>{h.create_time}</span>
                {h.dataset_id && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>数据集 #{h.dataset_id}</span>}
                <span style={{ flex: 1 }} />
                <span style={{ color: viewingHist === h.id ? 'var(--accent)' : 'var(--text-muted)', fontSize: 11 }}>
                  {viewingHist === h.id ? '查看中' : '查看'}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .dashboard-body { padding: 10px 8px 30px !important; }
        }
      `}</style>
    </div>
  )
}
