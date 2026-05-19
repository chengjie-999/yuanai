import { useState, useEffect } from 'react'
import { fetchDatasets, fetchDatasetAnalysis, getToken } from '../api'

const ANALYSIS_DS_KEY = 'analysisDsId'

function getLastDsId(): number {
  try { return Number(localStorage.getItem(ANALYSIS_DS_KEY)) || 0 } catch { return 0 }
}
function saveLastDsId(id: number) {
  localStorage.setItem(ANALYSIS_DS_KEY, String(id))
}

export default function DataAnalysisPage() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [dsId, setDsId] = useState<number>(getLastDsId)
  const [analysis, setAnalysis] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [expandedImg, setExpandedImg] = useState<string | null>(null)
  const [imgScale, setImgScale] = useState(1)
  const [drag, setDrag] = useState({ active: false, x: 0, y: 0, startX: 0, startY: 0 })

  useEffect(() => {
    fetchDatasets().then((data) => {
      setDatasets(data)
      const lastId = getLastDsId()
      const target = data.find((d: any) => d.id === lastId) ? lastId : (data[0]?.id || 0)
      setDsId(target)
      if (target) {
        fetchDatasetAnalysis(target, false, false).then((a) => { if (a) setAnalysis(a) })
      }
    })
  }, [])

  const handleSelect = (id: number) => {
    setDsId(id)
    saveLastDsId(id)
    setAnalysis(null)
    fetchDatasetAnalysis(id, false, false).then((a) => { if (a) setAnalysis(a) })
  }

  const handleAnalyze = async (force = false) => {
    if (!dsId) return
    setLoading(true)
    const data = await fetchDatasetAnalysis(dsId, false, force)
    if (data) setAnalysis(data)
    setLoading(false)
  }

  const handleCharts = async () => {
    if (!dsId) return
    setLoading(true)
    const data = await fetchDatasetAnalysis(dsId, true, false)
    if (data) setAnalysis(data)
    setLoading(false)
  }

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '20px 24px', background: '#f8f9fb' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54', whiteSpace: 'nowrap' }}>📊 数据分析</h2>
        <select value={dsId} onChange={(e) => handleSelect(Number(e.target.value))}
          style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', minWidth: 200 }}>
          <option value={0}>选择数据集...</option>
          {datasets.map((ds) => (
            <option key={ds.id} value={ds.id}>{ds.name} ({ds.row_count}行)</option>
          ))}
        </select>
      </div>

      {!dsId && datasets.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>暂无数据集，请先在「数据工作台」上传文件</div>
      )}

      {/* basic info — always shown, instant */}
      {/* analysis trigger */}
      {dsId > 0 && (
        <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
          <button onClick={() => handleAnalyze(false)} disabled={loading}
            className="btn btn-primary" style={{ padding: '8px 20px', fontSize: 14, fontWeight: 600, opacity: loading ? 0.6 : 1 }}>
            {loading ? '分析中...' : '📈 基础分析'}
          </button>
          {analysis && (
            <button onClick={() => handleCharts()} disabled={loading}
              style={{ padding: '8px 16px', fontSize: 13, border: '1px solid #ddd', borderRadius: 6, background: '#fff', cursor: 'pointer', opacity: loading ? 0.6 : 1 }}>
              {loading ? '生成中...' : '📊 生成图表'}
            </button>
          )}
        </div>
      )}

      {loading && <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>正在分析，请稍候...</div>}

      {/* analysis results */}
      {analysis && !loading && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px,1fr))', gap: 12, marginBottom: 16 }}>
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
              {Object.entries(analysis.missing).map(([col, cnt]: [string, any]) => (
                <span key={col} style={{ background: '#ffebee', color: '#c62828', padding: '4px 10px', borderRadius: 4, fontSize: 12, marginRight: 8 }}>{col}: {cnt}</span>
              ))}
            </Section>
          )}

          {analysis.corr && analysis.corr.length > 0 && (
            <Section title="相关性矩阵">
              <div style={{ overflow: 'auto' }}>
                <table style={{ borderCollapse: 'collapse', fontSize: 11 }}>
                  <thead>
                    <tr><th style={th}></th>
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
              <img src={`${ch.url}?token=${getToken()}`} style={{ maxWidth: '100%', borderRadius: 6, cursor: 'pointer' }}
                onClick={() => setExpandedImg(`${ch.url}?token=${getToken()}`)} />
            </Section>
          ))}
        </>
      )}
      {expandedImg && (
        <div onClick={() => { setExpandedImg(null); setImgScale(1); setDrag({ active: false, x: 0, y: 0, startX: 0, startY: 0 }) }}
          onWheel={(e) => { e.stopPropagation(); setImgScale((s) => Math.max(0.3, Math.min(8, s + (e.deltaY > 0 ? -0.4 : 0.4)))) }}
          onMouseMove={(e) => { if (drag.active) setDrag((d) => ({ ...d, x: e.clientX - d.startX, y: e.clientY - d.startY })) }}
          onMouseUp={() => setDrag((d) => ({ ...d, active: false }))}
          style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: drag.active ? 'grabbing' : 'grab', overflow: 'hidden' }}>
          <img src={expandedImg} onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => { e.stopPropagation(); setDrag({ active: true, x: drag.x, y: drag.y, startX: e.clientX - drag.x, startY: e.clientY - drag.y }) }}
            onDragStart={(e) => e.preventDefault()}
            style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 8px 40px rgba(0,0,0,0.5)', transform: `translate(${drag.x}px,${drag.y}px) scale(${imgScale})`, cursor: drag.active ? 'grabbing' : 'grab', userSelect: 'none' }} />
        </div>
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

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: '14px 16px', textAlign: 'center' }}>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>{label}</div>
    </div>
  )
}
