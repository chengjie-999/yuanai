import { useState, useEffect } from 'react'
import { API_BASE, headers, safeJson, authHeaders } from '../api'
import { SUB_AGENTS } from '../config/agents'
import { ErrorBoundary } from './ErrorBoundary'

/* 我的用量卡（2026-10-30）：用户本人 API 成本展示——只展示计费价
   （真实成本为平台内部口径，普通用户不显示）。
   金额格式：常规两位小数；<0.01 的小金额保留两位有效数字（不显示成 ¥0.00）。
   加载失败静默不显示（成本展示非关键路径）。 */
type UsageData = {
  billed_month: number; billed_total: number
  paid: number; outstanding: number
  arrears_limit: number
  month_calls: number; total_calls: number
}

// 金额格式化（2026-10-30 用户拍板）：≥0.01 两位小数；更小的保留两位有效数字
const fmtCost = (v: number): string => {
  if (!v || v <= 0) return '0.00'
  if (v >= 0.01) return v.toFixed(2)
  return String(Number(v.toPrecision(2)))
}

// 带符号金额（显示金额余额口径）：负=欠费，正=余额；浮点尘埃按零
const fmtCostSigned = (v: number): string =>
  Math.abs(v) < 0.0001 ? '¥0.00' : (v < 0 ? `-¥${fmtCost(-v)}` : `¥${fmtCost(v)}`)

function MyUsageCard() {
  const [data, setData] = useState<UsageData | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/auth/cost`, { headers: authHeaders() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then(setData)
      .catch(() => { /* 静默 */ })
  }, [])

  if (!data) return null
  const stat = (label: string, value: string, sub: string, color?: string) => (
    <div style={{ flex: 1, textAlign: 'center', padding: '4px 8px' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || 'var(--accent)', lineHeight: 1.3 }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{label}</div>
      <div style={{ fontSize: 10.5, color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>
    </div>
  )
  const owe = data.paid - data.billed_total < 0
  return (
    <div style={_C.card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={_C.title}>我的用量 <span style={_C.sub}>— 本人 API 成本（近 30 天）</span></div>
        <a href="/chat/billing" style={{ padding: '5px 14px', marginRight: 14, borderRadius: 999,
          background: 'var(--accent)', color: '#fff', fontSize: 12.5, fontWeight: 600, textDecoration: 'none' }}>
          充值
        </a>
      </div>
      <div style={{ display: 'flex', padding: '16px 12px' }}>
        {/* 2026-10-30 口径（与用户管理同款）：显示金额 = 收款 − 系数成本，
            欠费红/余额绿 */}
        {stat('本月应计', `¥${fmtCost(data.billed_month)}`, '')}
        {stat('累计应计', `¥${fmtCost(data.billed_total)}`, '')}
        {stat('累计已收', `¥${fmtCost(data.paid)}`, '')}
        {stat('显示金额', `${fmtCostSigned(data.paid - data.billed_total)}`,
          owe ? `负=欠费（满 ¥${data.arrears_limit || 20} 限制使用）` : '正=余额',
          owe ? 'var(--danger)' : 'var(--success)')}
        {stat('本月调用', `${data.month_calls} 次`, `累计 ${data.total_calls} 次`)}
      </div>
    </div>
  )
}





/* 本地 Agent 下载卡（2026-10-30，自设置页迁入 /chat/agent）：版本列表 + 自服务安装码 +
   使用指南（图形/终端两套入口）；管理员管理版本在后台「Agent 管理」。 */
const _C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
}

/* 本地 Agent 下载卡（2026-10-30）：普通用户下载入口——全部版本可下（默认标记）、
   自服务安装码（生成即预绑定，安装后自动归属本账号）；管理员管理版本在后台上传。 */
function AgentDownloadCard() {
  const [data, setData] = useState<{ default_version: string; versions: any[] } | null>(null)
  const [code, setCode] = useState<{ code: string; bound: boolean; message: string; machine_name?: string; device_count?: number; max_devices?: number; machine_names?: string[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [copied, setCopied] = useState(false)

  const loadData = () => {
    fetch(`${API_BASE}/agent/downloads`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => {})
  }
  const loadCode = () => {
    fetch(`${API_BASE}/agent/my-code`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then(setCode)
      .catch(() => {})
  }
  useEffect(() => {
    loadData()
    loadCode()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const resetCode = async () => {
    if (busy) return
    setBusy(true); setMsg('')
    const res = await fetch(`${API_BASE}/agent/my-code`, { method: 'POST', headers: authHeaders() })
    const d = await res.json().catch(() => ({}))
    setBusy(false)
    if (res.ok && d.code) { setCode({ code: d.code, bound: false, message: d.message }); setMsg('') }
    else setMsg(d.detail || '重置失败')
  }

  const copyCode = async () => {
    if (!code?.code) return
    try { await navigator.clipboard.writeText(code.code) } catch { /* 忽略 */ }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div style={_C.card}>
      <div style={_C.title}>本地 Agent 下载 <span style={_C.sub}>— 下载后在本机运行，数据在本机计算</span></div>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-light)' }}>
        {code?.bound ? (
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            本账号已绑定 {code.device_count || '多'} 台设备（上限 {code.max_devices || 10} 台：
            {code.machine_names?.join('、') || ''}）——换新电脑请先在后台解绑旧设备。
            <button onClick={resetCode} disabled={busy}
              style={{ marginLeft: 8, padding: '4px 12px', borderRadius: 6, border: '1px solid var(--accent)', background: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
              {busy ? '生成中...' : '重置安装码'}
            </button>
          </div>
        ) : code?.code ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              你的安装码{code.device_count ? `（本账号已绑定 ${code.device_count} 台设备，新码用于另一台电脑）` : ''}
            </span>
            <code style={{ fontFamily: 'monospace', fontSize: 14, fontWeight: 700, color: 'var(--accent)', background: 'var(--bg-secondary)', padding: '6px 12px', borderRadius: 6 }}>{code.code}</code>
            <button onClick={copyCode} title="复制" aria-label="复制"
              style={{ padding: '5px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--text-primary)' }}>
              {copied ? '已复制' : '复制'}
            </button>
            <button onClick={resetCode} disabled={busy}
              style={{ padding: '5px 12px', borderRadius: 6, border: '1px solid var(--accent)', background: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
              {busy ? '生成中...' : '重新生成'}
            </button>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>安装码加载中...</div>
        )}
        {msg && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 6 }}>{msg}</div>}
        {/* 使用指南（2026-10-30 用户拍板：图形 + yuan/yuancc 终端两套入口） */}
        <div style={{ marginTop: 10, padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.9 }}>
          <b style={{ color: 'var(--text-primary)' }}>使用指南</b>
          <div>① <b>图形安装（推荐）</b>：下载默认版本（文件名已内嵌安装码）→ 双击运行 → 自动注册完成（托盘常驻，可开关各 Agent；文件名被改才会弹码框）</div>
          <div>② <b>终端安装（开发者，本机需 Python 3.10+ 环境）</b>：</div>
          <div style={{ fontFamily: 'monospace', fontSize: 11.5, paddingLeft: 18, color: 'var(--text-primary)' }}>
            yuan --install &lt;安装码&gt;&nbsp;&nbsp;注册本机设备（之后 yuan 自动联动云端）
            <br />yuan --tray&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;托盘常驻（含桌宠/计划执行一体）
            <br />yuan --update&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;下载默认版本安装包（sha256 校验）
            <br />yuancc&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Claude Code 原生终端（需本机装有 claude 命令）
          </div>
        </div>
      </div>
      <div style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>版本列表（默认版本优先推荐）</div>
          <div style={{ flex: 1 }} />
          <button onClick={() => { loadData(); loadCode() }} title="刷新" aria-label="刷新"
            style={{ fontSize: 12, padding: '3px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            刷新
          </button>
        </div>
        {/* 默认版本醒目下载入口（2026-10-30 用户反馈：无版本时也要有明确入口）；
            T2（2026-11-06）：有自服务安装码时走带码下载——文件名内嵌安装码，
            首启零输码零弹窗静默注册；无码保持原静态下载 */}
        {data && data.default_version ? (() => {
          const d = data.versions.find((v) => v.version === data.default_version)
          const withCode = !!code?.code && !code.bound
          return d ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <a href={withCode
                ? `/api/v1/agent/download-exe?code=${encodeURIComponent(code!.code)}`
                : `/downloads/versions/${d.filename}`} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '10px 18px', borderRadius: 8, background: 'var(--accent)', color: '#fff',
                textDecoration: 'none', fontSize: 13.5, fontWeight: 600, marginBottom: 6,
              }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                </svg>
                下载默认版本 v{d.version}（{(d.size / 1024 / 1024).toFixed(0)}MB）
              </a>
              {withCode && (
                <div style={{ fontSize: 11.5, color: 'var(--success)', marginBottom: 8 }}>
                  已绑定你的账号：文件名内嵌安装码，双击后自动注册，无需手动输入
                </div>
              )}
            </div>
          ) : null
        })() : null}
        {!data || data.versions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '14px 0', fontSize: 12, color: 'var(--text-muted)' }}>
            暂无可用版本——请点右上「刷新」重试，或联系管理员在后台「Agent 管理」发布版本
          </div>
        ) : (
          data.versions.map((v) => (
            <div key={v.version} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--border-light)', fontSize: 12.5 }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>v{v.version}</span>
              {v.version === data.default_version && (
                <span style={{ fontSize: 11, color: '#fff', background: 'var(--accent)', padding: '1px 8px', borderRadius: 999 }}>默认</span>
              )}
              <span style={{ color: 'var(--text-muted)', flex: 1 }}>{(v.size / 1024 / 1024).toFixed(0)}MB · {v.uploaded_at?.slice(0, 10)}</span>
              {v.note && <span style={{ color: 'var(--text-muted)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.note}>{v.note}</span>}
              <a href={(code?.code && !code.bound && v.version === data.default_version)
                ? `/api/v1/agent/download-exe?code=${encodeURIComponent(code.code)}`
                : `/downloads/versions/${v.filename}`}
                style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>下载</a>
            </div>
          ))
        )}
      </div>
    </div>
  )
}


export default function AgentPage({ userId }: { userId?: number }) {
  const [agents, setAgents] = useState<any[]>([])

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/agent-status`, { headers: headers() })
      const data = await safeJson(res)
      if (Array.isArray(data)) setAgents(data)
    } catch {}
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  // 后端已按用户过滤（旧模式 agent_id==user_id + 设备一对一绑定），前端不再
  // 用 agent_id==userId 二次过滤——设备模式 agent_id 是设备号，曾把在线 Agent
  // 滤成空导致页面显示离线/待连接。取法同 AgentStatus：优先匹配，否则取第一个。
  const matched = agents.find((a: any) => String(a.agent_id) === String(userId))
  const myAgents = userId ? (matched ? [matched] : agents.slice(0, 1)) : agents.slice(0, 1)
  const mainOnline = myAgents.length > 0 && myAgents[0].online
  const mainAgent = myAgents[0]

  return (
    <ErrorBoundary>
    <div style={{ background: 'var(--bg-secondary)', padding: '40px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 560, width: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* 我的用量（2026-10-30 用户拍板：与 Agent 写一起）：应计/已收/显示金额/调用 */}
        <MyUsageCard />

        {/* 下载与安装（2026-10-30 自设置页迁入）：版本列表 + 安装码 + 使用指南 */}
        <AgentDownloadCard />

        {/* 运行状态 */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 12, height: 12, borderRadius: '50%',
              background: mainOnline ? 'var(--success)' : 'var(--text-muted)',
              display: 'inline-block',
              boxShadow: mainOnline ? '0 0 8px rgba(76,175,80,0.4)' : undefined,
            }} />
            <span style={{ fontWeight: 600, fontSize: 16, color: mainOnline ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
              {mainOnline ? '本地Agent 运行中' : '本地Agent 离线'}
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={load} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)' }}>刷新</button>
          </div>
          {mainOnline && mainAgent && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 16 }}>
              <span>{mainAgent.agent_name}</span>
              <span style={{ color: 'var(--text-muted)' }}>|</span>
              <span style={{ fontFamily: 'monospace' }}>ID: {mainAgent.agent_id}</span>
              <span style={{ color: 'var(--text-muted)' }}>|</span>
              <span>心跳: {mainAgent.last_heartbeat}</span>
            </div>
          )}
          {!mainOnline && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              <p style={{ margin: 0 }}>请在本机启动 小元AI Agent 客户端，启动后将自动连接云端。</p>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>如未安装，请在本页顶部「本地 Agent 下载」自取安装包与安装码。</p>
            </div>
          )}
        </div>

        {/* 能力矩阵 */}
        <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{ padding: '14px 24px', borderBottom: '1px solid var(--border-light)', fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', background: 'var(--bg-secondary)' }}>
            能力矩阵
          </div>
          {SUB_AGENTS.map((sa) => (
            <div key={sa.key} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '14px 24px',
              borderBottom: '1px solid var(--border-light)',
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', background: mainOnline ? sa.color : 'var(--text-muted)',
                display: 'inline-block', flexShrink: 0,
              }} />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13, color: sa.color }}>{sa.label}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 1 }}>{sa.desc}</div>
              </div>
              <div style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: mainOnline ? 'var(--success)' : 'var(--text-secondary)' }}>
                {mainOnline ? '就绪' : '待连接'}
              </span>
            </div>
          ))}
        </div>

        {/* 活动记录 */}
        {myAgents.map((a, i) => {
          const acts = a.activities || []
          if (acts.length === 0) return null
          return (
            <div key={i} style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', padding: '16px 24px' }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 8 }}>活动记录</div>
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {acts.map((act: any, j: number) => (
                  <div key={j} style={{
                    padding: '6px 0', borderBottom: j < acts.length - 1 ? '1px solid var(--border-light)' : 'none',
                    display: 'flex', gap: 8, alignItems: 'flex-start',
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 48, flexShrink: 0 }}>{act.time}</span>
                    <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>{act.message}</span>
                    {act.detail && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{act.detail}</span>}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
    </ErrorBoundary>
  )
}
