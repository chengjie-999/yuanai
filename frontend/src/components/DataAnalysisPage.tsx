import { useState, useEffect } from 'react'
import { fetchStats } from '../api'

function MetricCard({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div style={{ flex: 1, padding: '16px 20px', borderRadius: 10, background: color, minWidth: 140 }}>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', marginBottom: 2 }}>{value}</div>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>{sub}</div>
    </div>
  )
}

function BarChart({ data, height = 80 }: { data: { label: string; value: number }[]; height?: number }) {
  const max = Math.max(...data.map((d) => d.value), 1)
  const w = Math.max(data.length * 30, 200)
  return (
    <svg width={w} height={height} style={{ display: 'block' }}>
      {data.map((d, i) => {
        const barH = (d.value / max) * (height - 10)
        const x = i * (w / data.length) + 4
        const bw = Math.max(w / data.length - 8, 4)
        return (
          <g key={i}>
            <rect x={x} y={height - 10 - barH} width={bw} height={barH} rx={2} fill="#1976d2" opacity={0.7} />
          </g>
        )
      })}
    </svg>
  )
}

export default function DataAnalysisPage() {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats().then((data) => {
      setStats(data)
      setLoading(false)
    })
  }, [])

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中...</div>
  if (!stats) return <div style={{ padding: 40, textAlign: 'center', color: '#e53935' }}>获取数据失败</div>

  const dailyMessages = (stats.daily_messages || []).map((d: any) => ({ label: d.date.slice(5), value: d.count }))

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '20px 24px', gap: 16, overflow: 'auto', boxSizing: 'border-box' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>📊 数据总览</h2>

      {/* 概览卡片 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <MetricCard label="用户数" value={`${stats.users}`} sub="注册用户总量" color="#1976d2" />
        <MetricCard label="聊天会话" value={`${stats.sessions}`} sub={`共 ${stats.messages} 条消息`} color="#388e3c" />
        <MetricCard label="平均每会话" value={`${stats.avg_messages_per_session}`} sub="消息数" color="#f57c00" />
        <MetricCard label="审核记录" value={`${stats.task_images}`} sub="已保存的审核图片" color="#7b1fa2" />
        <MetricCard label="截图缓存" value={`${stats.cache_size_mb} MB`} sub="data/qimg/" color="#e53935" />
        <MetricCard label="数据文件" value={`${(stats.excel_files || []).length}`} sub="xlsx / csv" color="#00897b" />
      </div>

      {/* Excel / CSV 文件列表 */}
      {(stats.excel_files || []).length > 0 && (
        <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12 }}>📁 数据文件</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f9f9f9' }}>
                  <th style={thStyle}>文件</th>
                  <th style={thStyle}>大小</th>
                </tr>
              </thead>
              <tbody>
                {(stats.excel_files || []).map((f: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                    <td style={tdStyle}>{f.name}</td>
                    <td style={tdStyle}>{f.size_kb} KB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 每日消息趋势 */}
      <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12 }}>近30天每日消息量</div>
        {dailyMessages.length > 0 ? (
          <>
            <div style={{ overflowX: 'auto' }}>
              <BarChart data={dailyMessages} height={100} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#999', marginTop: 4 }}>
              <span>{dailyMessages[0]?.label || ''}</span>
              <span>{dailyMessages[dailyMessages.length - 1]?.label || ''}</span>
            </div>
          </>
        ) : (
          <div style={{ color: '#999', fontSize: 13, padding: 20, textAlign: 'center' }}>暂无数据</div>
        )}
      </div>

      {/* 数据明细表格 */}
      <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12 }}>数据明细</div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f9f9f9' }}>
                <th style={{ padding: '8px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #eee' }}>指标</th>
                <th style={{ padding: '8px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #eee' }}>数值</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['用户总数', stats.users],
                ['聊天会话数', stats.sessions],
                ['总消息数', stats.messages],
                ['平均每会话消息数', stats.avg_messages_per_session],
                ['审核图片记录', stats.task_images],
                ['图片缓存大小', `${stats.cache_size_mb} MB`],
              ].map(([label, value], i) => (
                <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '8px 14px', color: '#333' }}>{label}</td>
                  <td style={{ padding: '8px 14px', color: '#1976d2', fontWeight: 600 }}>{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const thStyle: React.CSSProperties = { padding: '8px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #eee' }
const tdStyle: React.CSSProperties = { padding: '8px 14px', fontSize: 13, color: '#333' }
