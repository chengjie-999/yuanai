import { useMemo, useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from 'recharts'

/* 表格 → 交互图表（2026-10-26，贴数据分析定位）：
   markdown 表格 / ```csv 代码块的「图表化」面板——
   数值列自动识别，X 轴 / Y 轴（最多 3 列）/ 柱状折线可切换。
   recharts 经调用方 lazy import（本组件只被 TableBlock 动态加载，不进主包）。 */

const SERIES_COLORS = ['var(--accent)', 'var(--success)', 'var(--warning)']

function isNumericCol(values: string[]): boolean {
  const nums = values.filter((v) => v !== '' && !Number.isNaN(Number(v)))
  return nums.length > 0 && nums.length >= values.length * 0.8
}

export default function TableChart({ headers, rows }: { headers: string[]; rows: string[][] }) {
  const numericCols = useMemo(
    () => headers.map((h, i) => ({ h, i, num: isNumericCol(rows.map((r) => r[i] || '')) })),
    [headers, rows])
  const numCols = numericCols.filter((c) => c.num)

  const [xIdx, setXIdx] = useState(0)
  const [yIdxs, setYIdxs] = useState<number[]>(
    numCols.length >= 2 ? [numCols[0].i, numCols[1].i] : [numCols[0]?.i ?? 0].filter((i) => i >= 0))
  const [type, setType] = useState<'bar' | 'line'>('bar')

  if (numCols.length < 1) {
    return (
      <div style={{ padding: '12px 0', fontSize: 12, color: 'var(--text-muted)' }}>
        没有可绘制的数值列（需至少一列数字数据）
      </div>
    )
  }

  const data = rows.map((r) => {
    const o: Record<string, string | number> = {}
    headers.forEach((h, i) => { o[h] = numCols.some((c) => c.i === i) ? Number(r[i] || 0) : (r[i] || '') })
    return o
  })
  const xKey = headers[xIdx]
  const yKeys = yIdxs.map((i) => headers[i]).filter(Boolean).slice(0, 3)
  const Chart = type === 'bar' ? BarChart : LineChart

  return (
    <div style={{ padding: '4px 0 8px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', fontSize: 12 }}>
        <label style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
          X 轴
          <select value={xIdx} onChange={(e) => setXIdx(Number(e.target.value))}
            style={{ padding: '3px 6px', borderRadius: 6, border: '1px solid var(--border)',
                     background: 'var(--bg-input)', color: 'var(--text-primary)', fontSize: 12 }}>
            {headers.map((h, i) => <option key={i} value={i}>{h}</option>)}
          </select>
        </label>
        <label style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
          Y 轴（可多选）
          <select multiple value={yIdxs.map(String)} onChange={(e) => {
            const vals = Array.from(e.target.selectedOptions).map((o) => Number(o.value))
            if (vals.length) setYIdxs(vals.slice(0, 3))
          }}
            style={{ padding: '3px 6px', borderRadius: 6, border: '1px solid var(--border)',
                     background: 'var(--bg-input)', color: 'var(--text-primary)', fontSize: 12,
                     maxWidth: 180 }}>
            {numCols.map((c) => <option key={c.i} value={c.i}>{c.h}</option>)}
          </select>
        </label>
        <span style={{ display: 'flex', gap: 2 }}>
          {(['bar', 'line'] as const).map((t) => (
            <button key={t} onClick={() => setType(t)}
              style={{ padding: '3px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                       border: `1px solid ${type === t ? 'var(--accent)' : 'var(--border)'}`,
                       background: type === t ? 'var(--accent-light)' : 'var(--bg-input)',
                       color: type === t ? 'var(--accent)' : 'var(--text-secondary)' }}>
              {t === 'bar' ? '柱状图' : '折线图'}
            </button>
          ))}
        </span>
      </div>
      <div style={{ width: '100%', height: 260, marginTop: 8 }}>
        <ResponsiveContainer>
          <Chart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-light)" />
            <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
            <YAxis tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} width={48} />
            <Tooltip contentStyle={{
              background: 'var(--bg-input)', border: '1px solid var(--border)',
              borderRadius: 8, fontSize: 12, color: 'var(--text-primary)',
            }} />
            {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
            {yKeys.map((k, i) => (
              type === 'bar' ? (
                <Bar key={k} dataKey={k} fill={SERIES_COLORS[i % 3]} radius={[3, 3, 0, 0]} />
              ) : (
                <Line key={k} dataKey={k} stroke={SERIES_COLORS[i % 3]}
                  strokeWidth={2} dot={{ r: 2.5 }} />
              )
            ))}
          </Chart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
