import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle, headers, API_BASE } from './shared'

// 本机开发 → 代理到 8000；线上 → 当前站点 wss
const getServerUrl = () =>
  ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'ws://localhost:8000'
    : `wss://${window.location.hostname}`

const installCommand = (code: string) =>
  `python -m agent.main --install ${code} --server-url ${getServerUrl()}`

function CopyBtn({ text, label = '复制安装命令' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // 剪贴板 API 不可用时降级
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button onClick={copy}
      style={{
        padding: '3px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
        border: '1px solid var(--border)', background: copied ? '#4caf5022' : 'var(--bg-tertiary)',
        color: copied ? '#4caf50' : 'var(--text-primary)', whiteSpace: 'nowrap',
      }}>
      {copied ? '✓ 已复制' : label}
    </button>
  )
}

export default function AgentDevicesTab() {
  const [devices, setDevices] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [codeCount, setCodeCount] = useState(1)
  const [newCodes, setNewCodes] = useState<string[]>([])
  const [bindUserId, setBindUserId] = useState<Record<number, string>>({})

  const fetchDevices = async () => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/agent-devices`, { headers: headers() })
      if (!res.ok) throw new Error()
      setDevices(await res.json())
    } catch { setError('获取设备列表失败') }
    setLoading(false)
  }

  useEffect(() => {
    fetchDevices()
    const t = setInterval(fetchDevices, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/admin/users`, { headers: headers() })
      .then((r) => r.ok ? r.json() : [])
      .then((list) => setUsers(list))
      .catch(() => {})
  }, [])

  const genCodes = async () => {
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/agent-codes`, {
        method: 'POST', headers: headers(), body: JSON.stringify({ count: codeCount }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || '生成失败'); return }
      setNewCodes(data.codes || [])
      fetchDevices()
    } catch { setError('生成失败') }
  }

  const postJson = async (url: string, body: any) => {
    const res = await fetch(url, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
    const data = await res.json()
    if (!res.ok) { setError(data.detail || '操作失败'); return null }
    fetchDevices()
    return data
  }

  const handleBind = (agentId: number) => {
    const uid = bindUserId[agentId]
    if (!uid) { setError('请先选择要绑定的用户'); return }
    postJson(`${API_BASE}/admin/agent-bind`, { agent_id: agentId, user_id: Number(uid) })
  }

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={fetchDevices} />}

      {/* 下载安装包（傻瓜流程：下载 → 双击 → 弹窗输安装码） */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>下载本机 Agent 安装包</div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <a href="/downloads/yuanai-agent.exe" style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 18px', borderRadius: 8, background: 'var(--accent)', color: '#fff',
            textDecoration: 'none', fontSize: 13, fontWeight: 600,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
            下载（Windows）
          </a>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            用户使用流程：下载 → 双击运行 → 弹出窗口粘贴安装码 → 完成（托盘常驻，可选开关各 Agent）
          </span>
        </div>
      </Card>

      {/* 生成安装码 */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>签发安装码</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>数量</span>
          <input type="number" min={1} max={50} value={codeCount}
            onChange={(e) => setCodeCount(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
            style={{ ...inputStyle, width: 80 }} />
          <button onClick={genCodes} style={btnPrimary}>生成</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            发给用户后：已装安装包 → 托盘菜单「重新注册」输码；未装 → 命令行 <code>python -m agent.main --install 安装码</code>
          </span>
        </div>
        {newCodes.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>新安装码：</div>
            {newCodes.map((c) => (
              <div key={c} style={{
                display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap',
              }}>
                <span style={{
                  fontFamily: 'monospace', fontSize: 14, padding: '6px 10px',
                  background: 'var(--bg-tertiary)', borderRadius: 6, letterSpacing: 1,
                }}>{c}</span>
                <CopyBtn text={installCommand(c)} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 设备列表 */}
      {loading ? <Spinner /> : devices.length === 0 ? <Empty msg="暂无设备" /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--bg-tertiary)' }}>
                {['ID', '安装码', '机器名', '状态', '绑定用户', '在线', '最后在线', '操作'].map((h) => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.agent_id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 10px' }}>#{d.agent_id}</td>
                  <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 12 }}>
                    {d.install_code}
                    {!d.registered && (
                      <div style={{ marginTop: 4 }}>
                        <CopyBtn text={installCommand(d.install_code)} />
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '8px 10px' }}>{d.machine_name || '-'}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{
                      fontSize: 12, padding: '2px 8px', borderRadius: 10,
                      background: d.registered ? '#4caf5022' : 'var(--bg-tertiary)',
                      color: d.registered ? '#4caf50' : 'var(--text-muted)',
                    }}>{d.registered ? '已注册' : '未注册'}</span>
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    {d.user_id ? (
                      <span>{d.username} (#{d.user_id})</span>
                    ) : d.registered ? (
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <select value={bindUserId[d.agent_id] || ''}
                          onChange={(e) => setBindUserId((p) => ({ ...p, [d.agent_id]: e.target.value }))}
                          style={{ padding: '5px 8px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg-input)', color: 'var(--text-primary)', outline: 'none' }}>
                          <option value="">选择用户…</option>
                          {users.map((u) => <option key={u.id} value={u.id}>{u.username} (#{u.id})</option>)}
                        </select>
                        <button onClick={() => handleBind(d.agent_id)}
                          style={{ ...btnPrimary, padding: '4px 12px', fontSize: 12 }}>绑定</button>
                      </div>
                    ) : <span style={{ color: 'var(--text-muted)' }}>-</span>}
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: '50%', display: 'inline-block', marginRight: 4,
                      background: d.online ? 'var(--success)' : 'var(--text-muted)',
                    }} />
                    {d.online ? '在线' : '离线'}
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)' }}>{d.last_seen || '-'}</td>
                  <td style={{ padding: '8px 10px' }}>
                    {d.user_id && (
                      <button onClick={() => postJson(`${API_BASE}/admin/agent-unbind`, { agent_id: d.agent_id })}
                        style={{ ...btnDangerSm, marginRight: 6 }}>解绑</button>
                    )}
                    <button onClick={() => postJson(`${API_BASE}/admin/agent-freeze`, { agent_id: d.agent_id, enabled: d.enabled ? 0 : 1 })}
                      style={{ ...btnDangerSm, background: d.enabled ? undefined : '#4caf50' }}>
                      {d.enabled ? '冻结' : '解冻'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
