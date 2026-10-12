/* ============================================================
   结构化结果渲染块（从 AnalysisDashboard 抽出，分析大屏与计划页共用）
   - 标量 → KPI 卡；长文本 → 段落；list[dict] → 表格；嵌套 dict → 分组
   - 已知键位（RFM/回归/时序/流失/相关）给中文标题；主题跟随 CSS 变量
   ============================================================ */

// 已知键位 → 中文标题（未知键原样展示）
export const KEY_LABELS: Record<string, string> = {
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
  result: '结果摘要',
}

const isNumber = (v: any): v is number => typeof v === 'number' && isFinite(v)
const isShortString = (v: any): v is string => typeof v === 'string' && v.length <= 60

export const fmt = (v: any): string => {
  if (isNumber(v)) return v.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
  return String(v)
}

export const labelOf = (key: string) => KEY_LABELS[key] || key

/** 单条 KPI 卡：数值重墨、标签轻灰 */
export function KpiCard({ label, value }: { label: string; value: any }) {
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

/** list[dict] → 表格（前 50 行） */
export function DataTable({ title, rows }: { title: string; rows: Record<string, any>[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).slice(0, 12)
  const shown = rows.slice(0, 50)
  return (
    <div style={{ marginBottom: 14 }}>
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
export function RenderValue({ k, v }: { k: string; v: any }) {
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

export function renderBody(obj: Record<string, any>) {
  return Object.entries(obj).map(([k, v]) => <RenderValue key={k} k={k} v={v} />)
}
