import { useState, useEffect, useRef } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle, headers, API_BASE } from './shared'
import { getToken } from '../../api'

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

  // ---- 已发布安装包信息（version.json） ----
  const [pkgInfo, setPkgInfo] = useState<{ version: string; size: number } | null>(null)

  const loadPkgInfo = () => {
    fetch('/downloads/version.json', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d?.version) setPkgInfo(d); else setPkgInfo(null) })
      .catch(() => setPkgInfo(null))
  }

  // ---- 安装包上传（拖拽 + XHR 带进度，发布即分发） ----
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [uploadMsg, setUploadMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const uploadExeFile = (f: File) => {
    setUploadBusy(true); setUploadPct(0); setUploadMsg('')
    const fd = new FormData()
    fd.append('version', '')  // 留空 = 后端自动按上传时间生成版本号
    fd.append('file', f)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/admin/agent-exe-upload`)
    xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`)
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) setUploadPct(Math.round((ev.loaded / ev.total) * 100))
    }
    xhr.onload = () => {
      setUploadBusy(false)
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status === 200 && data.ok) { setUploadMsg(`✓ 已发布 v${data.version}（${(data.size / 1024 / 1024).toFixed(0)}MB）`); loadPkgInfo() }
        else setUploadMsg(data.detail || '上传失败')
      } catch { setUploadMsg(`上传失败 HTTP ${xhr.status}`) }
    }
    xhr.onerror = () => { setUploadBusy(false); setUploadMsg('上传失败，网络错误') }
    xhr.send(fd)
  }

  const handleUploadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (f) uploadExeFile(f)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) uploadExeFile(f)
  }

  // 上传期间刷新/关闭页面时弹浏览器确认，防止手滑中断
  useEffect(() => {
    if (!uploadBusy) return
    const guard = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [uploadBusy])

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
    loadPkgInfo()
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

      {/* 安装包发布：下载 + 上传新版本（上传即发布，客户端自动更新） */}
      <Card>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>本机 Agent 安装包</div>
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
          {pkgInfo ? (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              当前版本 <b style={{ color: 'var(--text-primary)' }}>v{pkgInfo.version}</b> · {(pkgInfo.size / 1024 / 1024).toFixed(0)}MB
            </span>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>尚未发布安装包</span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            用户使用流程：下载 → 双击运行 → 弹出窗口粘贴安装码 → 完成（托盘常驻，可选开关各 Agent）
          </span>
        </div>
        {/* 上传新版本（拖拽上传，发布即分发：客户端托盘自动检查 version.json 更新） */}
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--border)' }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: 'var(--text-primary)' }}>发布新版本</div>
          <input ref={fileRef} type="file" accept=".exe" hidden onChange={handleUploadFile} />
          <div
            onClick={() => !uploadBusy && fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 10, padding: '22px 16px', textAlign: 'center', cursor: uploadBusy ? 'not-allowed' : 'pointer',
              background: dragOver ? 'var(--accent-light)' : 'var(--bg-secondary)',
              transition: 'all 0.15s', maxWidth: 460,
            }}
          >
            {uploadBusy ? (
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 8 }}>正在上传 {uploadPct}%</div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${uploadPct}%`, background: 'var(--accent)', transition: 'width 0.2s' }} />
                </div>
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                <div style={{ fontSize: 22, marginBottom: 4 }}>📦</div>
                <b style={{ color: 'var(--text-primary)' }}>把 yuanai-agent.exe 拖到这里</b>（或点击选择文件）
              </div>
            )}
          </div>
          {uploadMsg && <div style={{ fontSize: 12, marginTop: 8, color: uploadMsg.startsWith('✓') ? 'var(--success)' : 'var(--danger)' }}>{uploadMsg}</div>}
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
            版本号自动生成 · 上传后立即生效：所有已安装的客户端会在托盘里提示「发现新版本」，点一下自动更新
            <br />上传中请勿刷新或关闭页面（切换到其他页不影响，会在后台继续上传）
          </div>
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
                {/* 傻瓜模式：默认复制纯安装码（exe 弹窗/托盘重注册直接用）；命令行方式保留备选 */}
                <CopyBtn text={c} label="复制安装码" />
                <CopyBtn text={installCommand(c)} label="复制命令行" />
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
                      <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <CopyBtn text={d.install_code} label="复制安装码" />
                        <CopyBtn text={installCommand(d.install_code)} label="复制命令行" />
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
