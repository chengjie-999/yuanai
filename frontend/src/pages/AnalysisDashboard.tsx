import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { API_BASE, getToken } from '../api'
import { useSecuredUrl } from '../components/chat/helpers'
import { ArrowLeftIcon, BarChartIcon } from '../components/icons'

/* ============================================================
   通用分析大屏：任意分析脚本的 __RESULT__ JSON → 统一渲染
   - 标量 → KPI 卡；长文本 → 段落；list[dict] → 表格；嵌套 dict → 分组
   - 已知键位（RFM/回归/时序/流失/相关）给中文标题
   - 主题跟随 CSS 变量；移动端自适应；数据过期时后端自动从历史恢复
   ============================================================ */

// 已知键位 → 中文标题（未知键原样展示）
const KEY_LABELS: Record<string, string> = {
  summary: '总体概览',
  means: '均值指标',
  segments: '分群结果',
  train_test: '训练/测试结果',
  coefficients: '模型系数',
  anomalies: '异常检测',
  rolling: '滚动统计',
  corr: '相关系数',
  auc: 'AUC 指标',
  confusion_matrix: '混淆矩阵',
  metrics: '评估指标',
  kpis: '关键指标',
}

const isNumber = (v: any): v is number => typeof v === 'number' && isFinite(v)
const isShortString = (v: any): v is string => typeof v === 'string' && v.length <= 60

const fmt = (v: any): string => {
  if (isNumber(v)) return v.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
  return String(v)
}

const labelOf = (key: string) => KEY_LABELS[key] || key

/** 单条 KPI 卡：文本用文字令牌，数值重墨 */
function KpiCard({ label, value }: { label: string; value: any }) {
  return (
    <div style={{
      background: 'var(--bg-primary)', borderRadius: 10, border: '1px solid var(--border)',
      padding: '12px 14px', minWidth: 110, flex: '1 1 130px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.3, wordBreak: 'break-all' }}>{fmt(value)}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{label}</div>
    </div>
  )
}

/** list[dict] → 表格（前 50 行；行文本用文字令牌） */
function DataTable({ title, rows }: { title: string; rows: Record<string, any>[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).slice(0, 12)
  const shown = rows.slice(0, 50)
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{title}</div>
      <div style={{ overflow: 'auto', border: '1px solid var(--border)', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c} style={{ padding: '6px 10px', textAlign: 'left', fontSize: 11, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', fontWeight: 600 }}>{labelOf(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c} style={{ padding: '5px 10px', color: 'var(--text-primary)', borderBottom: '1px solid var(--border-light)', whiteSpace: 'nowrap', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{fmt(r[c] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 50 && (
          <div style={{ padding: '6px 10px', fontSize: 11, color: 'var(--text-muted)' }}>仅显示前 50 行（共 {rows.length} 行）</div>
        )}
      </div>
    </div>
  )
}

/** 递归渲染器：任意 JSON 值 → UI */
function RenderValue({ k, v }: { k: string; v: any }) {
  if (v === null || v === undefined) return null
  if (isNumber(v) || isShortString(v)) {
    return <KpiCard label={labelOf(k)} value={v} />
  }
  if (typeof v === 'string') {
    return (
      <div style={{ flex: '1 1 100%', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>{labelOf(k)}</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{v}</div>
      </div>
    )
  }
  if (Array.isArray(v)) {
    if (v.length > 0 && v.every((x) => x && typeof x === 'object' && !Array.isArray(x))) {
      return <DataTable title={labelOf(k)} rows={v as Record<string, any>[]} />
    }
    if (v.length > 0 && v.every((x) => isNumber(x) || isShortString(x))) {
      return (
        <div style={{ flex: '1 1 100%', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>{labelOf(k)}</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {v.slice(0, 30).map((x, i) => (
              <span key={i} style={{ fontSize: 12, padding: '3px 10px', borderRadius: 12, background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>{fmt(x)}</span>
            ))}
          </div>
        </div>
      )
    }
    return null
  }
  if (typeof v === 'object') {
    // 嵌套 dict → 递归分组
    return (
      <div style={{ flex: '1 1 100%' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', margin: '4px 0 10px' }}>{labelOf(k)}</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>{renderBody(v)}</div>
      </div>
    )
  }
  return <KpiCard label={labelOf(k)} value={v} />
}

function renderBody(obj: Record<string, any>) {
  return Object.entries(obj).map(([k, v]) => <RenderValue key={k} k={k} v={v} />)
}

export default function AnalysisDashboard() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [data, setData] = useState<any>(null)
  const [meta, setMeta] = useState<{ recovered?: boolean; created_at?: string }>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
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
      })
      .catch((e) => {
        setError(e.message === 'NOT_FOUND' ? '未找到大屏数据：请先在对话中完成一次分析' : '大屏加载失败，请稍后重试')
      })
      .finally(() => setLoading(false))
  }, [sessionId])

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
        <Link to="/chat" style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: 13, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1 }}><ArrowLeftIcon size={13} /> 返回</Link>
        <span style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)' }}>分析大屏</span>
        {created_at && (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            数据时间 {created_at}{meta.recovered ? '（已从历史恢复）' : ''}
          </span>
        )}
        <div style={{ flex: 1 }} />
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
      </div>

      <style>{`
        @media (max-width: 768px) {
          .dashboard-body { padding: 10px 8px 30px !important; }
        }
      `}</style>
    </div>
  )
}
