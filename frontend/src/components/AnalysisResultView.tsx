const thStyle: React.CSSProperties = {
  padding: '4px 6px', textAlign: 'left', fontSize: 10,
  color: 'var(--text-secondary)', fontWeight: 600,
  borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
}
const tdStyle: React.CSSProperties = {
  padding: '3px 6px', fontSize: 10, color: 'var(--text-primary)',
  borderBottom: '1px solid var(--border-light)', whiteSpace: 'nowrap',
}

export default function AnalysisResultView({ analysis }: { analysis: any }) {
  const { name, row_count, columns, num_cols, describe, missing, corr, corr_labels, charts } = analysis

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{name}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
          {row_count} 行 · {columns?.length || 0} 列 · {num_cols?.length || 0} 数值列
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
