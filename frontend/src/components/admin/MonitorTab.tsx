import { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts'
import { Spinner, ErrorMsg, Card, CardHeader, Empty, headers, API_BASE } from './shared'
import { fetchMonitorStatus, fetchMonitorChanges, fetchMonitorTimeline, fetchMonitorFileTypes } from '../../api'

const CHART_GREEN = '#629755'
const CHART_RED = '#bc3f3c'
const CHART_CYAN = '#589df6'
const CHART_ORANGE = '#f5a623'

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}分${s}秒`
}

function fmtTime(iso: string): string {
  return iso.slice(11, 19)
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload) return null
  return (
    <div style={{
      background: 'var(--bg-primary)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '8px 12px', fontSize: 12, color: 'var(--text-primary)',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      {payload.map((entry: any, i: number) => (
        <div key={i} style={{ color: entry.color }}>{entry.name}: {entry.value}</div>
      ))}
    </div>
  )
}

function SummaryCard({ label, value, color, unit }: {
  label: string; value: string | number; color: string; unit?: string
}) {
  return (
    <div style={{
      background: 'var(--bg-primary)', borderRadius: 12,
      border: '1px solid var(--border)', padding: '14px 12px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color, lineHeight: 1.3 }}>
        {value ?? '-'}<span style={{ fontSize: 12, fontWeight: 400, marginLeft: 4 }}>{unit}</span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

function OverviewItem({ label, value, unit }: {
  label: string; value: string | number; unit?: string
}) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 8, padding: '8px 12px',
      fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'baseline', gap: 4,
    }}>
      <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 15 }}>{value}</span>
      {unit && <span>{unit}</span>}
      <span style={{ marginLeft: 'auto' }}>{label}</span>
    </div>
  )
}

export default function MonitorTab() {
  const [status, setStatus] = useState<any>(null)
  const [changes, setChanges] = useState<any[]>([])
  const [timeline, setTimeline] = useState<any[]>([])
  const [fileTypes, setFileTypes] = useState<any[]>([])
  const [mostChanged, setMostChanged] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadAll = () => {
    fetch(`${API_BASE}/monitor/snapshot?limit=100`, { headers: headers() })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => {
        setStatus(d.status)
        setChanges(d.changes || [])
        setTimeline(d.timeline || [])
        setFileTypes(d.file_types || [])
        setMostChanged(d.most_changed || [])
        setError('')
      })
      .catch(() => setError('加载监控数据失败'))
      .finally(() => setLoading(false))
  }

  // ---- 监控控制端点（api/index.ts 未封装 start/stop/report/top-files，仿其 fetch 写法写在组件内） ----
  const monitorStart = async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/monitor/start`, { method: 'POST', headers: headers() })
      return res.ok
    } catch { return false }
  }

  const monitorStop = async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/monitor/stop`, { method: 'POST', headers: headers() })
      return res.ok
    } catch { return false }
  }

  const fetchMonitorTopFiles = async (topN: number = 10): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE}/monitor/top-files?top_n=${topN}`, { headers: headers() })
      if (!res.ok) return { top_files: [] }
      return await res.json()
    } catch { return { top_files: [] } }
  }

  // ---- 监控控制数据（status / changes / timeline / file-types / top-files 各端点） ----
  const [ctrlStatus, setCtrlStatus] = useState<any>(null)
  const [ctrlChanges, setCtrlChanges] = useState<any>(null)
  const [ctrlTimeline, setCtrlTimeline] = useState<any>(null)
  const [ctrlFileTypes, setCtrlFileTypes] = useState<any>(null)
  const [ctrlTopFiles, setCtrlTopFiles] = useState<any>(null)
  const [ctrlBusy, setCtrlBusy] = useState('')  // 正在执行的控制操作: start/stop
  const [ctrlMsg, setCtrlMsg] = useState('')    // 控制操作结果提示

  const loadControls = () => {
    fetchMonitorStatus().then(setCtrlStatus)
    fetchMonitorChanges(50).then(setCtrlChanges)
    fetchMonitorTimeline().then(setCtrlTimeline)
    fetchMonitorFileTypes().then(setCtrlFileTypes)
    fetchMonitorTopFiles(10).then(setCtrlTopFiles)
  }

  // 注意：POST /monitor/report 是 Agent 变更上报通道（非报告生成），
  // 前端不提供入口，避免注入脏数据
  const handleMonitorAction = async (action: 'start' | 'stop') => {
    setCtrlBusy(action)
    setCtrlMsg('')
    const ok = action === 'start' ? await monitorStart() : await monitorStop()
    if (ok) {
      setCtrlMsg(action === 'start' ? '监控已启动' : '监控已停止')
      loadControls()  // 刷新端点数据
      loadAll()       // 刷新快照展示
    } else {
      setCtrlMsg('操作失败，请重试')
    }
    setCtrlBusy('')
  }

  useEffect(() => {
    loadAll()
    loadControls()
    const interval = setInterval(loadAll, 10000)
    return () => clearInterval(interval)
  }, [])

  const chartData = useMemo(() => {
    return timeline.slice(-50).map((pt: any) => ({
      time: fmtTime(pt.timestamp),
      added: pt.cumulative_lines_added,
      removed: pt.cumulative_lines_removed,
      files: pt.cumulative_files,
    }))
  }, [timeline])

  if (loading) return <Spinner />

  const s = status || {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {error && <ErrorMsg msg={error} onRetry={loadAll} />}

      {s.git_available === false && (
        <div style={{
          padding: '12px 16px', borderRadius: 8,
          background: 'rgba(188,63,60,0.1)', color: 'var(--danger)',
          fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>&#9888;</span>
          <span>未检测到 Git 仓库或 Git 未安装。代码监控需要 Git 支持。</span>
        </div>
      )}

      {/* 监控控制：启动/停止 + 各独立端点数据概览 */}
      <Card>
        <CardHeader title="监控控制" action={
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 10,
            color: ctrlStatus?.monitoring ? CHART_GREEN : 'var(--text-muted)',
            background: ctrlStatus?.monitoring ? `${CHART_GREEN}20` : 'var(--bg-tertiary)',
          }}>
            {ctrlStatus?.monitoring ? '● 监控中' : '○ 已停止'}
          </span>
        } />
        <div style={{ padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={() => handleMonitorAction('start')}
              disabled={ctrlBusy !== '' || ctrlStatus?.monitoring}
              style={{
                padding: '7px 14px', borderRadius: 6, border: 'none', fontSize: 13,
                background: ctrlStatus?.monitoring ? 'var(--bg-tertiary)' : 'var(--accent)',
                color: ctrlStatus?.monitoring ? 'var(--text-muted)' : '#fff',
                cursor: ctrlBusy === '' && !ctrlStatus?.monitoring ? 'pointer' : 'not-allowed',
              }}
            >
              {ctrlBusy === 'start' ? '启动中...' : '▶ 启动监控'}
            </button>
            <button
              onClick={() => handleMonitorAction('stop')}
              disabled={ctrlBusy !== '' || !ctrlStatus?.monitoring}
              style={{
                padding: '7px 14px', borderRadius: 6, fontSize: 13,
                border: '1px solid var(--danger)', background: 'none', color: 'var(--danger)',
                cursor: ctrlBusy === '' && ctrlStatus?.monitoring ? 'pointer' : 'not-allowed',
              }}
            >
              {ctrlBusy === 'stop' ? '停止中...' : '⏹ 停止监控'}
            </button>
            {ctrlMsg && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{ctrlMsg}</span>}
          </div>

          {/* GET /monitor/status 状态详情 */}
          {ctrlStatus && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              <span>Git: {ctrlStatus.git_available ? '可用' : '不可用'}</span>
              {ctrlStatus.start_time && <span>开始时间: {ctrlStatus.start_time.slice(0, 19).replace('T', ' ')}</span>}
              <span>监控时长: {formatDuration(ctrlStatus.duration_seconds || 0)}</span>
              <span>变更文件: {ctrlStatus.total_files_changed ?? 0}</span>
            </div>
          )}

          {/* changes / timeline / file-types / top-files 端点概览 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 }}>
            <OverviewItem label="已记录变更" value={ctrlChanges?.total ?? '-'} unit="条" />
            <OverviewItem label="时间线采样" value={ctrlTimeline?.timeline?.length ?? '-'} unit="点" />
            <OverviewItem label="文件类型" value={ctrlFileTypes?.distributions?.length ?? '-'} unit="种" />
            <OverviewItem label="Top 文件" value={ctrlTopFiles?.top_files?.length ?? '-'} unit="个" />
          </div>

          {/* 文件类型 Top3 + 变更文件 Top3 预览 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>文件类型 Top3</div>
              {(ctrlFileTypes?.distributions || []).slice(0, 3).map((t: any) => (
                <div key={t.extension} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' }}>
                  <span style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{t.extension}</span>
                  <span style={{ color: 'var(--text-muted)' }}>{t.count} 次 · {t.percentage}%</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>变更文件 Top3</div>
              {(ctrlTopFiles?.top_files || []).slice(0, 3).map((f: any) => (
                <div key={f.filepath} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, padding: '3px 0' }}>
                  <span style={{
                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    fontFamily: 'monospace', color: 'var(--text-primary)',
                  }} title={f.filepath}>{f.filepath}</span>
                  <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{f.change_count} 次</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Summary Cards */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12,
      }}>
        <SummaryCard label="文件变更数" value={s.total_files_changed ?? '-'} color={CHART_CYAN} />
        <SummaryCard label="新增行数" value={s.total_lines_added ?? '-'} color={CHART_GREEN} />
        <SummaryCard label="删除行数" value={s.total_lines_removed ?? '-'} color={CHART_RED} />
        <SummaryCard label="变更速度" value={s.change_velocity ?? '-'} color={CHART_ORANGE} unit="行/分" />
      </div>

      {s.start_time && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 16 }}>
          <span>监控时长: {formatDuration(s.duration_seconds || 0)}</span>
          <span>事件总数: {s.recent_changes_count || 0}</span>
        </div>
      )}

      {/* Row 1: AreaChart + BarChart */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card>
          <CardHeader title="累积行数变化趋势" />
          <div style={{ padding: 16 }}>
            {chartData.length === 0 ? (
              <Empty msg="等待代码变更..." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorAdded" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_GREEN} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CHART_GREEN} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorRemoved" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_RED} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CHART_RED} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone" dataKey="added" name="新增"
                    stroke={CHART_GREEN} fill="url(#colorAdded)" strokeWidth={2}
                  />
                  <Area
                    type="monotone" dataKey="removed" name="删除"
                    stroke={CHART_RED} fill="url(#colorRemoved)" strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="文件类型分布" />
          <div style={{ padding: 16 }}>
            {fileTypes.length === 0 ? (
              <Empty msg="暂无数据" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={fileTypes} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                  <YAxis
                    type="category" dataKey="extension"
                    tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={60}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="count" name="变更次数" fill={CHART_CYAN} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {/* Row 2: Most changed files + Recent activity */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card>
          <CardHeader title="最常变更文件" />
          {mostChanged.length === 0 ? (
            <Empty msg="暂无变更" />
          ) : (
            <div>
              {mostChanged.map((item, i) => (
                <div key={item.filepath} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 16px',
                  borderBottom: i < mostChanged.length - 1 ? '1px solid var(--border-light)' : 'none',
                  fontSize: 12,
                }}>
                  <span style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: 'var(--accent-light)', color: 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 600, flexShrink: 0,
                  }}>{i + 1}</span>
                  <span style={{
                    flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap', color: 'var(--text-primary)',
                    fontFamily: 'monospace', fontSize: 12,
                  }} title={item.filepath}>{item.filepath}</span>
                  <span style={{
                    background: 'var(--accent-light)', color: 'var(--accent)',
                    padding: '1px 8px', borderRadius: 10, fontSize: 11,
                    fontWeight: 600, whiteSpace: 'nowrap',
                  }}>{item.count} 次</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="最近活动" action={
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {changes.length > 0 ? `最近 ${Math.min(changes.length, 100)} 条` : ''}
            </span>
          } />
          <div style={{ maxHeight: 280, overflow: 'auto' }}>
            {changes.length === 0 ? (
              <Empty msg="等待代码变更..." />
            ) : (
              changes.slice(0, 100).map((c: any, i: number) => {
                const statusLabel =
                  c.status_label === 'untracked' ? '新增' :
                  c.status_label === 'modified' ? '修改' :
                  c.status_label === 'added' ? '新增' :
                  c.status_label === 'deleted' ? '删除' :
                  c.status_label === 'renamed' ? '重命名' : c.status_label
                const statusColor =
                  c.status === 'A' || c.status === '??' ? CHART_GREEN :
                  c.status === 'D' ? CHART_RED :
                  c.status === 'M' ? CHART_CYAN :
                  c.status === 'R' ? CHART_ORANGE : 'var(--text-muted)'
                return (
                  <div key={`${c.filepath}-${i}`} style={{
                    display: 'flex', gap: 8, padding: '6px 16px',
                    borderBottom: i < Math.min(changes.length, 100) - 1
                      ? '1px solid var(--border-light)' : 'none',
                    fontSize: 11, alignItems: 'center',
                  }}>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '1px 6px',
                      borderRadius: 4, whiteSpace: 'nowrap', flexShrink: 0,
                      background: `${statusColor}20`, color: statusColor,
                    }}>{statusLabel}</span>
                    <span style={{
                      flex: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', color: 'var(--text-primary)',
                      fontFamily: 'monospace', fontSize: 11,
                    }} title={c.filepath}>{c.filepath}</span>
                    <span style={{
                      color: 'var(--text-muted)', fontSize: 10,
                      whiteSpace: 'nowrap', flexShrink: 0,
                    }}>{fmtTime(c.timestamp)}</span>
                  </div>
                )
              })
            )}
          </div>
        </Card>
      </div>

      {s.git_available !== false && changes.length === 0 && !error && (
        <div style={{
          textAlign: 'center', color: 'var(--text-muted)',
          padding: 40, fontSize: 13,
        }}>
          暂无代码变更记录。当 AI 在项目中创建或修改文件时，变更将实时显示在此处。
        </div>
      )}
    </div>
  )
}
