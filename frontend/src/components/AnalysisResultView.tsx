import { API_BASE } from '../api'

const thStyle: React.CSSProperties = {
  padding: '4px 6px', textAlign: 'left', fontSize: 10,
  color: 'var(--text-secondary)', fontWeight: 600,
  borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
}
const tdStyle: React.CSSProperties = {
  padding: '3px 6px', fontSize: 10, color: 'var(--text-primary)',
  borderBottom: '1px solid var(--border-light)', whiteSpace: 'nowrap',
}

function exportUrl(dsId: number, format: string) {
  return `${API_BASE}/data/export/${dsId}?format=${format}`
}

export default function AnalysisResultView({ analysis }: { analysis: any }) {
  const { id, name, row_count, columns, num_cols, describe, missing, corr, corr_labels, charts, time_series } = analysis

  return (
    <div>
      {/* Header + export buttons */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
            {row_count} 行 · {columns?.length || 0} 列 · {num_cols?.length || 0} 数值列
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <a href={exportUrl(id, 'excel')} download
            style={{ fontSize: 11, padding: '4px 10px', borderRadius: 4, border: '1px solid var(--border)',
              background: 'var(--bg-secondary)', color: 'var(--text-secondary)', textDecoration: 'none', cursor: 'pointer' }}>
            📥 Excel
          </a>
          <a href={exportUrl(id, 'html')} download
            style={{ fontSize: 11, padding: '4px 10px', borderRadius: 4, border: '1px solid var(--border)',
              background: 'var(--bg-secondary)', color: 'var(--text-secondary)', textDecoration: 'none', cursor: 'pointer' }}>
            🌐 HTML
          </a>
        </div>
      </div>

      {describe && Object.keys(describe).length > 0 && (
        <div style={{ marginBottom: 14, overflow: 'auto' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>数值列统计</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr>
                <th style={thStyle}>列名</th>
                {Object.keys(Object.values(describe)[0] || {}).map((k) => (
                  <th key={k} style={thStyle}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(describe).map(([col, stats]: [string, any], i) => (
                <tr key={col} style={{ background: i % 2 === 0 ? 'var(--bg-secondary)' : 'transparent' }}>
                  <td style={tdStyle}>{col}</td>
                  {Object.values(stats).map((v: any, j) => (
                    <td key={j} style={tdStyle}>{typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2)) : String(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {missing && Object.keys(missing).length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>缺失值</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(missing).map(([col, cnt]: [string, any]) => (
              <span key={col} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>
                {col}: {cnt}
              </span>
            ))}
          </div>
        </div>
      )}

      {corr && corr.length > 0 && corr_labels && (
        <div style={{ marginBottom: 14, overflow: 'auto' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>相关系数矩阵</div>
          <table style={{ borderCollapse: 'collapse', fontSize: 10 }}>
            <thead>
              <tr>
                <th style={thStyle}></th>
                {corr_labels.map((l: string) => <th key={l} style={{ ...thStyle, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={l}>{l}</th>)}
              </tr>
            </thead>
            <tbody>
              {corr.map((row: number[], i: number) => (
                <tr key={i}>
                  <td style={{ ...tdStyle, fontWeight: 600, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={corr_labels[i]}>{corr_labels[i]}</td>
                  {row.map((v, j) => (
                    <td key={j} style={{ ...tdStyle, background: `rgba(88,157,246,${Math.abs(v) * 0.15})` }}>{v.toFixed(2)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Time series section */}
      {time_series && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
            时间序列分析 · {time_series.date_col}
          </div>

          {time_series.rolling && (
            <div style={{ marginBottom: 10, overflow: 'auto' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>7天滚动统计（最近50行）</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10 }}>
                <thead>
                  <tr>
                    <th style={thStyle}>日期</th>
                    <th style={thStyle}>均值</th>
                    <th style={thStyle}>标准差</th>
                  </tr>
                </thead>
                <tbody>
                  {time_series.rolling.date.slice(-10).map((d: string, i: number) => (
                    <tr key={i}>
                      <td style={tdStyle}>{d.slice(0, 10)}</td>
                      <td style={tdStyle}>{time_series.rolling.mean_7d[time_series.rolling.date.length - 10 + i]?.toFixed(2)}</td>
                      <td style={tdStyle}>{time_series.rolling.std_7d[time_series.rolling.date.length - 10 + i]?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {time_series.anomalies && time_series.anomalies.length > 0 && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, color: 'var(--danger)', marginBottom: 4 }}>异常点 ({time_series.anomalies.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {time_series.anomalies.map((a: any, i: number) => (
                  <span key={i} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: 'rgba(188,63,60,0.1)', color: 'var(--danger)' }}>
                    {a.date?.slice(0, 10)}: {a.value?.toFixed(1)} (z={a.z_score})
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {charts?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>图表 ({charts.length})</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {charts.map((ch: any, i: number) => (
              <div key={i} style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)', background: 'var(--bg-primary)' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 10px', background: 'var(--bg-secondary)' }}>
                  {ch.name}
                </div>
                {ch.html_url ? (
                  <iframe src={ch.html_url} style={{ width: '100%', height: 300, border: 'none' }} />
                ) : ch.data ? (
                  <img src={`data:image/png;base64,${ch.data}`} style={{ width: '100%', display: 'block' }} alt={ch.name} />
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
