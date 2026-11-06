import { useState, useEffect, useRef } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, btnDangerSm, inputStyle, headers, API_BASE } from './shared'
import { uploadFileWithProgress } from '../../api'
import { useAuth } from '../../contexts/AuthContext'
import { PackageIcon } from '../icons'

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
    <button onClick={copy} title={copied ? '已复制' : label} aria-label={copied ? '已复制' : label}
      style={{
        padding: '3px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
        border: '1px solid var(--border)', background: copied ? 'var(--success-soft)' : 'var(--bg-tertiary)',
        color: copied ? 'var(--success)' : 'var(--text-primary)', whiteSpace: 'nowrap',
      }}>
      {copied ? '✓ 已复制' : label}
    </button>
  )
}

export default function AgentDevicesTab() {
  const { user } = useAuth()
  const [devices, setDevices] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [codeCount, setCodeCount] = useState(1)
  const [newCodes, setNewCodes] = useState<string[]>([])
  const [bindUserId, setBindUserId] = useState<Record<number, string>>({})
  // 长令牌签发（发布 Agent 安装包用：本地打包脚本 --upload 鉴权）
  const [tokenUserId, setTokenUserId] = useState<number | ''>('')
  const [tokenDays, setTokenDays] = useState(90)
  const [mintedToken, setMintedToken] = useState('')
  const [tokenMsg, setTokenMsg] = useState('')

  // ---- Agent 版本清单（2026-10-30 多版本保留：上传不覆盖，全部留存可回退） ----
  const [versions, setVersions] = useState<any[]>([])
  const [defaultVersion, setDefaultVersion] = useState('')
  const [upVersion, setUpVersion] = useState('')
  const [upNote, setUpNote] = useState('')

  const loadVersions = () => {
    fetch(`${API_BASE}/admin/agent-versions`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) { setVersions(d.versions || []); setDefaultVersion(d.default_version || '') }
      })
      .catch(() => {})
  }

  // ---- 安装包上传（拖拽 + XHR 带进度，发布即进版本库） ----
  const [uploadBusy, setUploadBusy] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [uploadMsg, setUploadMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const uploadExeFile = (f: File) => {
    setUploadBusy(true); setUploadPct(0); setUploadMsg('')
    // 统一上传收口（2026-11-06）：大文件走进度版（XHR onprogress）
    uploadFileWithProgress(
      '/admin/agent-exe-upload',
      { file: f },
      { version: upVersion.trim(), note: upNote.trim() },  // version 留空 = 后端自动生成
      (pct) => setUploadPct(pct),
    ).then((data: any) => {
      setUploadBusy(false)
      if (data.ok) {
        setUploadMsg(`已发布 v${data.version}（${(data.size / 1024 / 1024).toFixed(0)}MB）`)
        setUpVersion(''); setUpNote('')
        loadVersions()
      } else setUploadMsg(data.detail || '上传失败')
    }).catch((err: any) => {
      setUploadBusy(false)
      setUploadMsg(err.message || '上传失败，网络错误')
    })
  }

  const handleSetDefault = async (version: string) => {
    const res = await fetch(`${API_BASE}/admin/agent-versions/default`, {
      method: 'POST', headers: headers(), body: JSON.stringify({ version }),
    })
    const data = await res.json()
    if (!res.ok) { setError(data.detail || '设置失败'); return }
    loadVersions()
  }

  const handleDeleteVersion = async (version: string) => {
    if (!window.confirm(`确定删除版本 v${version}？删除后不可恢复。`)) return
    const res = await fetch(`${API_BASE}/admin/agent-versions/${version}`, {
      method: 'DELETE', headers: headers(),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      setError(data.detail || '删除失败')
      return
    }
    loadVersions()
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
    loadVersions()
    const t = setInterval(fetchDevices, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/admin/users`, { headers: headers() })
      .then((r) => r.ok ? r.json() : [])
      .then((list) => setUsers(list))
      .catch(() => {})
  }, [])

  const mintToken = async () => {
    setTokenMsg('')
    const uid = tokenUserId === '' ? (user?.id ?? 0) : Number(tokenUserId)
    if (!uid) { setTokenMsg('请选择用户'); return }
    const res = await fetch(`${API_BASE}/admin/agent-token`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ user_id: uid, expires_days: tokenDays }),
    })
    const data = await res.json()
    if (!res.ok) { setTokenMsg(data.detail || '签发失败'); return }
    setMintedToken(data.token || '')
  }

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
      <Card style={{ padding: '16px 20px' }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>本机 Agent 安装包</div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {defaultVersion ? (
            <a href={`/downloads/versions/yuanai-agent-v${defaultVersion}.exe`} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '8px 18px', borderRadius: 8, background: 'var(--accent)', color: '#fff',
              textDecoration: 'none', fontSize: 13, fontWeight: 600,
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
              </svg>
              下载默认版本（Windows）
            </a>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>尚未发布安装包</span>
          )}
          {defaultVersion && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              默认版本 <b style={{ color: 'var(--text-primary)' }}>v{defaultVersion}</b> · 共 {versions.length} 个版本
            </span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            用户使用流程：下载 → 双击运行 → 弹出窗口粘贴安装码 → 完成（托盘常驻，可选开关各 Agent）
          </span>
        </div>
        {/* 版本清单（2026-10-30 多版本保留：全部可下载/设为默认/删除） */}
        {versions.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginTop: 12 }}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', textAlign: 'left' }}>
                {['版本', '大小', '上传时间', '备注', '操作'].map((h) => (
                  <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.version} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    v{v.version}
                    {v.version === defaultVersion && (
                      <span style={{ fontSize: 11, color: 'var(--accent)', marginLeft: 6, fontWeight: 600 }}>默认</span>
                    )}
                  </td>
                  <td style={{ padding: '6px 8px', color: 'var(--text-secondary)' }}>{(v.size / 1024 / 1024).toFixed(0)}MB</td>
                  <td style={{ padding: '6px 8px', color: 'var(--text-muted)' }}>{v.uploaded_at?.slice(0, 16)}</td>
                  <td style={{ padding: '6px 8px', color: 'var(--text-secondary)' }}>{v.note || '—'}</td>
                  <td style={{ padding: '6px 8px', display: 'flex', gap: 6 }}>
                    <a href={`/downloads/versions/${v.filename}`} style={{ fontSize: 12, color: 'var(--accent)' }}>下载</a>
                    {v.version !== defaultVersion && (
                      <button onClick={() => handleSetDefault(v.version)} title="设为默认" aria-label="设为默认"
                        style={{ fontSize: 12, padding: '2px 8px', color: 'var(--accent)', border: '1px solid var(--accent)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>设为默认</button>
                    )}
                    {v.version !== defaultVersion && (
                      <button onClick={() => handleDeleteVersion(v.version)} title="删除" aria-label="删除"
                        style={{ fontSize: 12, padding: '2px 8px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer' }}>删除</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {/* 上传新版本（拖拽上传，多版本保留：同版本号覆盖，不同版本号新增） */}
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--border)' }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, color: 'var(--text-primary)' }}>发布新版本</div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <input value={upVersion} onChange={(e) => setUpVersion(e.target.value)} placeholder="版本号（留空自动生成，如 20261030）"
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', width: 250 }} />
            <input value={upNote} onChange={(e) => setUpNote(e.target.value)} maxLength={200} placeholder="备注（选填，如本次更新内容）"
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', width: 220 }} />
          </div>
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
                <div style={{ marginBottom: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}><PackageIcon size={22} /></div>
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
      <Card style={{ padding: '16px 20px' }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>签发安装码</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>数量</span>
          <input type="number" min={1} max={50} value={codeCount}
            onChange={(e) => setCodeCount(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
            style={{ ...inputStyle, width: 80 }} />
          <button onClick={genCodes} title="生成安装码" aria-label="生成安装码" style={btnPrimary}>生成</button>
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

      {/* 签发长令牌（2026-10-31：本地打包脚本 --upload 发布鉴权用） */}
      <Card style={{ padding: '16px 20px' }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>签发长令牌</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>用户</span>
          <select value={tokenUserId} onChange={(e) => setTokenUserId(e.target.value === '' ? '' : Number(e.target.value))}
            style={{ ...inputStyle, width: 200 }}>
            <option value="">当前管理员（自己）</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.username}（#{u.id}）</option>
            ))}
          </select>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>有效期</span>
          <input type="number" min={1} max={90} value={tokenDays}
            onChange={(e) => setTokenDays(Math.max(1, Math.min(90, Number(e.target.value) || 90)))}
            style={{ ...inputStyle, width: 80 }} />
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>天</span>
          <button onClick={mintToken} title="签发长令牌" aria-label="签发长令牌" style={btnPrimary}>签发</button>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            用途：本地打包脚本一键发布（<code>YUAN_ADMIN_TOKEN</code>）与 Agent 桥接
          </span>
        </div>
        {tokenMsg && <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)' }}>{tokenMsg}</div>}
        {mintedToken && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 12, color: 'var(--danger)', marginBottom: 6 }}>
              请立即复制保存——关闭页面后无法再次查看；令牌 90 天有效，可用 /admin/users/revoke-tokens 吊销
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{
                fontFamily: 'monospace', fontSize: 11, padding: '6px 10px',
                background: 'var(--bg-tertiary)', borderRadius: 6, wordBreak: 'break-all', maxWidth: 420,
              }}>{mintedToken}</span>
              <CopyBtn text={mintedToken} label="复制令牌" />
            </div>
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
                      background: d.registered ? 'var(--success-soft)' : 'var(--bg-tertiary)',
                      color: d.registered ? 'var(--success)' : 'var(--text-muted)',
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
                        <button onClick={() => handleBind(d.agent_id)} title="绑定用户" aria-label="绑定用户"
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
                      <button onClick={() => postJson(`${API_BASE}/admin/agent-unbind`, { agent_id: d.agent_id })} title="解绑" aria-label="解绑"
                        style={{ ...btnDangerSm, marginRight: 6 }}>解绑</button>
                    )}
                    <button className={d.enabled ? undefined : 'bg-success-solid'} onClick={() => postJson(`${API_BASE}/admin/agent-freeze`, { agent_id: d.agent_id, enabled: d.enabled ? 0 : 1 })} title={d.enabled ? '冻结' : '解冻'} aria-label={d.enabled ? '冻结' : '解冻'}
                      style={{ ...btnDangerSm, background: d.enabled ? undefined : 'var(--success)' }}>
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
