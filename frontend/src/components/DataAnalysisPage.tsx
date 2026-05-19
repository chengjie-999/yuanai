import { useState, useEffect, useCallback } from 'react'
import { fetchDatasets, fetchDatasetAnalysis } from '../api'

export default function DataAnalysisPage() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [dsId, setDsId] = useState<number>(0)
  const [analysis, setAnalysis] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const loadDatasets = useCallback(async () => {
    const data = await fetchDatasets()
    setDatasets(data)
    if (data.length > 0 && dsId === 0) setDsId(data[0].id)
  }, [])

  useEffect(() => { loadDatasets() }, [loadDatasets])

  useEffect(() => {
    if (dsId === 0) return
    setLoading(true)
    fetchDatasetAnalysis(dsId).then((data) => {
      setAnalysis(data)
      setLoading(false)
    })
  }, [dsId])

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '20px 24px', background: '#f8f9fb' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54', whiteSpace: 'nowrap' }}>📊 数据分析</h2>
        <select value={dsId} onChange={(e) => setDsId(Number(e.target.value))}
          style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', minWidth: 200 }}>
          <option value={0}>选择数据集...</option>
          {datasets.map((ds) => (
            <option key={ds.id} value={ds.id}>{ds.name} ({ds.row_count}行)</option>
          ))}
        </select>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>分析中...</div>}

      {analysis && !loading && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 12, marginBottom: 16 }}>
            <StatCard label="行数" value={analysis.row_count} color="#42a5f5" />
            <StatCard label="列数" value={analysis.columns?.length || 0} color="#66bb6a" />
            <StatCard label="数值列" value={analysis.num_cols?.length || 0} color="#ffa726" />
            <StatCard label="缺失列" value={Object.keys(analysis.missing || {}).length} color="#ef5350" />
          </div>

          {Object.keys(analysis.describe || {}).length > 0 && (
            <Section title="描述统计">
              <div style={{ overflow: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={th}>指标</th>
                      {Object.keys(analysis.describe).map((c: string) => <th key={c} style={th}>{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {['count','mean','std','min','25%','50%','75%','max'].map((stat) => (
                      <tr key={stat}>
                        <td style={td}><b>{stat}</b></td>
                        {Object.entries(analysis.describe).map(([col, vals]: [string, any]) => (
                          <td key={col} style={td}>{vals[stat]?.toFixed?.(2) ?? vals[stat] ?? '-'}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {Object.keys(analysis.missing || {}).length > 0 && (
            <Section title="缺失值">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {Object.entries(analysis.missing).map(([col, cnt]: [string, any]) => (
                  <span key={col} style={{ background: '#ffebee', color: '#c62828', padding: '4px 10px', borderRadius: 4, fontSize: 12 }}>{col}: {cnt}</span>
                ))}
              </div>
            </Section>
          )}

          {analysis.corr && analysis.corr.length > 0 && (
            <Section title="相关性矩阵">
              <div style={{ overflow: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th style={th}></th>
                      {analysis.corr_labels?.map((c: string) => <th key={c} style={th}>{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.corr.map((row: number[], ri: number) => (
                      <tr key={ri}>
                        <td style={td}><b>{analysis.corr_labels?.[ri]}</b></td>
                        {row.map((v, ci) => (
                          <td key={ci} style={{ ...td, background: `rgba(${v > 0 ? '66,165,245' : '239,83,80'},${Math.abs(v) * 0.15})` }}>{v.toFixed(2)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {analysis.charts?.map((ch: any, i: number) => (
            <Section key={i} title={ch.name}>
              <img src={`data:image/png;base64,${ch.data}`} style={{ maxWidth: '100%', borderRadius: 6 }} />
            </Section>
          ))}
        </>
      )}

      {!loading && !analysis && datasets.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>暂无数据集，请先在「数据工作台」上传文件</div>
      )}
    </div>
  )
}

const th: React.CSSProperties = { padding: '6px 10px', borderBottom: '2px solid #e0e0e0', color: '#555', textAlign: 'left', whiteSpace: 'nowrap' }
const td: React.CSSProperties = { padding: '4px 10px', borderBottom: '1px solid #f0f0f0', color: '#666', whiteSpace: 'nowrap' }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: 14, marginBottom: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 8px', color: '#333' }}>{title}</h3>
      {children}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '14px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{label}</div>
    </div>
  )
}
