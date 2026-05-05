import { useState, useEffect } from 'react'
import { fetchStats } from '../api'

function MetricCard({ label, value, sub, color, icon }: { label: string; value: string; sub: string; color: string; icon: string }) {
  return (
    <div style={{
      flex: 1, padding: '18px 20px', borderRadius: 10, background: color, minWidth: 150,
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)', transition: 'transform 0.15s, box-shadow 0.15s',
    }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.1)' }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)' }}
    >
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', marginBottom: 2, letterSpacing: 0.3 }}>{icon} {label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: '#fff', marginBottom: 2 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>{sub}</div>
    </div>
  )
}

function BarChart({ data, height = 80 }: { data: { label: string; value: number }[]; height?: number }) {
  const max = Math.max(...data.map((d) => d.value), 1)
  const w = Math.max(data.length * 30, 200)
  return (
    <svg width={w} height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7e57c2" stopOpacity={0.8} />
          <stop offset="100%" stopColor="#b39ddb" stopOpacity={0.6} />
        </linearGradient>
      </defs>
      {data.map((d, i) => {
        const barH = (d.value / max) * (height - 10)
        const x = i * (w / data.length) + 4
        const bw = Math.max(w / data.length - 8, 4)
        return (
          <g key={i}>
            <rect x={x} y={height - 10 - barH} width={bw} height={barH} rx={2} fill="url(#barGrad)" opacity={0.85} />
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

  if (loading) return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#b0b8c8', fontSize: 14 }}>
      <div style={{ textAlign: 'center' }}>
        <svg viewBox="0 0 100 100" width={48} height={48} style={{ marginBottom: 12, opacity: 0.4 }}>
          <circle cx="50" cy="52" r="28" fill="#1976d2" />
          <circle cx="50" cy="52" r="23" fill="#42a5f5" />
          {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#1976d2" strokeWidth="4" strokeLinecap="round" />
              <circle cx={x} cy={y} r="5" fill="#90caf9" />
            </g>
          ))}
          <ellipse cx="38" cy="44" rx="6" ry="7" fill="#fff" />
          <ellipse cx="38" cy="44" rx="3.5" ry="4.5" fill="#0d47a1" />
          <circle cx="40" cy="42" r="1.5" fill="#fff" opacity="0.9" />
          <path d="M54 44 Q59 38 64 44" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M42 60 Q50 68 58 60" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
          <ellipse cx="30" cy="54" rx="5" ry="3.5" fill="#f8bbd0" opacity="0.35" />
          <ellipse cx="70" cy="54" rx="5" ry="3.5" fill="#f8bbd0" opacity="0.35" />
        </svg>
        <div>加载中...</div>
      </div>
    </div>
  )
  if (!stats) return <div style={{ padding: 40, textAlign: 'center', color: '#e53935' }}>获取数据失败</div>

  const dailyMessages = (stats.daily_messages || []).map((d: any) => ({ label: d.date.slice(5), value: d.count }))

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 28px', gap: 16, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <svg viewBox="0 0 100 100" width={28} height={28}>
          <circle cx="50" cy="52" r="28" fill="#1976d2" />
          <circle cx="50" cy="52" r="23" fill="#42a5f5" />
          {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#1976d2" strokeWidth="4" strokeLinecap="round" />
              <circle cx={x} cy={y} r="5" fill="#90caf9" />
            </g>
          ))}
          <ellipse cx="38" cy="44" rx="6" ry="7" fill="#fff" />
          <ellipse cx="38" cy="44" rx="3.5" ry="4.5" fill="#0d47a1" />
          <circle cx="40" cy="42" r="1.5" fill="#fff" opacity="0.9" />
          <path d="M54 44 Q59 38 64 44" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M42 60 Q50 68 58 60" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
          <ellipse cx="30" cy="54" rx="5" ry="3.5" fill="#f8bbd0" opacity="0.35" />
          <ellipse cx="70" cy="54" rx="5" ry="3.5" fill="#f8bbd0" opacity="0.35" />
        </svg>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>数据总览</h2>
      </div>

      {/* 概览卡片 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <MetricCard label="用户数" value={`${stats.users}`} sub="注册用户总量" color="#5e35b1" icon="👤" />
        <MetricCard label="聊天会话" value={`${stats.sessions}`} sub={`共 ${stats.messages} 条消息`} color="#1976d2" icon="💬" />
        <MetricCard label="平均每会话" value={`${stats.avg_messages_per_session}`} sub="消息数" color="#f57c00" icon="📊" />
        <MetricCard label="审核记录" value={`${stats.task_images}`} sub="已保存的审核图片" color="#388e3c" icon="🎯" />
        <MetricCard label="截图缓存" value={`${stats.cache_size_mb} MB`} sub="data/qimg/" color="#e53935" icon="📦" />
        <MetricCard label="数据文件" value={`${(stats.excel_files || []).length}`} sub="xlsx / csv" color="#00897b" icon="📁" />
      </div>

      {/* 每日消息趋势 */}
      <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#7e57c2' }}>📈</span> 近30天每日消息量
        </div>
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

      {/* Excel / CSV 文件列表 */}
      {(stats.excel_files || []).length > 0 && (
        <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#00897b' }}>📁</span> 数据文件
          </div>
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
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 12 }}>{f.name}</td>
                    <td style={tdStyle}>{f.size_kb} KB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 数据明细表格 */}
      <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 10, padding: 16, boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#333', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#5e35b1' }}>📋</span> 数据明细
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f5f5f8' }}>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>指标</th>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600, borderBottom: '2px solid #e0e0e0' }}>数值</th>
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
                  <td style={{ padding: '10px 14px', color: '#333' }}>{label}</td>
                  <td style={{ padding: '10px 14px', color: '#5e35b1', fontWeight: 600 }}>{value}</td>
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
