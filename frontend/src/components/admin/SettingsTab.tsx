import { useState, useEffect } from 'react'
import { Card, CardHeader, headers, safeJson, API_BASE } from './shared'

const row: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 20px', borderBottom: '1px solid var(--border-light)', gap: 16,
}

const label: React.CSSProperties = { fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }
const hint: React.CSSProperties = { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }

const select: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)',
  fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', minWidth: 140,
}

const input: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)',
  fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', minWidth: 140,
}

// 系统参数字段清单（与后端 _SYSTEM_CONFIG_SCHEMA 对齐）
const PARAM_FIELDS: { key: string; label: string; hint: string; kind: 'number' | 'bool' | 'select' | 'text' | 'json'; choices?: string[]; step?: number }[] = [
  { key: 'memory_enabled', label: '记忆压缩总开关', hint: '关闭后对话不再折叠进长期记忆', kind: 'bool' },
  { key: 'memory_working_window', label: '工作记忆条数', hint: '最近 N 条原样保留不折叠', kind: 'number' },
  { key: 'memory_trigger_chars', label: '折叠触发字数', hint: '会话总字数超过该值触发折叠', kind: 'number' },
  { key: 'memory_fold_min_messages', label: '单次折叠最小条数', hint: '烧钱护栏：低于该条数不调 LLM', kind: 'number' },
  { key: 'memory_fold_min_chars', label: '单次折叠最小字数', hint: '低于该字数不调 LLM', kind: 'number' },
  { key: 'memory_fold_input_max_chars', label: '单次折叠输入上限', hint: '单次送给折叠模型的字数上限', kind: 'number' },
  { key: 'memory_max_items', label: '长期记忆条数上限', hint: '超限丢最旧', kind: 'number' },
  { key: 'memory_max_chars', label: '长期记忆字数上限', hint: '每轮注入系统提示的字数', kind: 'number' },
  { key: 'memory_fold_timeout_s', label: '折叠超时（秒）', hint: '折叠 LLM 调用超时', kind: 'number' },
  { key: 'memory_fold_daily_max', label: '每日折叠次数上限', hint: '每用户每天最多折叠次数', kind: 'number' },
  { key: 'memory_organize_delete_daily_max', label: '每日记忆删除上限', hint: '智能体自整理每天最多删几条（安全护栏）', kind: 'number' },
  { key: 'reasoning_effort', label: '推理强度默认', hint: 'DeepSeek 系列的默认思考深度', kind: 'select', choices: ['low', 'medium', 'high'] },
  { key: 'register_open', label: '公开注册', hint: '打开后 /auth/register 恢复注册入口', kind: 'bool' },
  { key: 'daily_message_quota', label: '每日消息配额', hint: '每用户每天消息数（0=不限）', kind: 'number' },
  { key: 'voice_enabled', label: '语音功能开关', hint: '关闭后通话与朗读返回 503', kind: 'bool' },
  { key: 'cost_profit_multiplier', label: '盈利系数', hint: '用户侧成本展示的计费系数：计费价 = 实际成本 × 系数（0.1-100）', kind: 'number', step: 0.1 },
  { key: 'arrears_limit', label: '欠费限制（元）', hint: '显示金额 ≤ -该值时限制聊天使用并提示缴费（0 = 不限制）', kind: 'number', step: 1 },
]

const PROMPT_FIELDS: { key: string; label: string; hint: string; rows?: number }[] = [
  { key: 'chat_system_prompt', label: '聊天系统提示词', hint: '空 = 使用前端内置默认提示词；保存后新对话生效', rows: 10 },
  { key: 'self_report_template', label: '模型自报模板', hint: '模型被问「你是什么模型」时的回答模板，{model} 占位为运行时真实模型 ID（不可造假）', rows: 3 },
  { key: 'capability_note', label: '能力说明备注', hint: '追加在系统提示词末尾的能力/边界说明', rows: 4 },
]

export default function SettingsTab() {
  // 设定中心（后端 _system_config）
  const [cfg, setCfg] = useState<Record<string, any>>({})
  const [effective, setEffective] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [saving, setSaving] = useState(false)

  const loadCfg = () => {
    fetch(`${API_BASE}/admin/system-config`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((d) => {
        const editable: Record<string, any> = {}
        for (const [k, v] of Object.entries(d.editable || {})) editable[k] = (v as any).value
        setCfg(editable)
        setEffective(d.effective)
      })
      .catch(() => {})
  }
  useEffect(() => { loadCfg() }, [])


  const handleSaveCfg = async () => {
    setSaving(true); setMsg('')
    const res = await fetch(`${API_BASE}/admin/system-config`, {
      method: 'PUT', headers: headers(), body: JSON.stringify({ system_config: cfg }),
    })
    const d = await safeJson(res)
    if (!res.ok) { setMsg(d?.detail || '保存失败') } else { setMsg('已保存，立即生效'); loadCfg() }
    setSaving(false)
  }

  const setVal = (key: string, v: any) => setCfg((p) => ({ ...p, [key]: v }))

  // ---- 更新公告（2026-10-31 用户拍板：网站部署与 Agent 版本更新各发一条） ----
  const [anns, setAnns] = useState<any[]>([])
  const [annKind, setAnnKind] = useState('site')
  const [annTitle, setAnnTitle] = useState('')
  const [annContent, setAnnContent] = useState('')
  const [annMsg, setAnnMsg] = useState('')

  const loadAnns = () => {
    fetch(`${API_BASE}/announcements?limit=20`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : []))
      .then(setAnns)
      .catch(() => {})
  }
  useEffect(() => { loadAnns() }, [])

  const publishAnn = async () => {
    if (!annTitle.trim() || !annContent.trim()) { setAnnMsg('请填写标题与内容'); return }
    const res = await fetch(`${API_BASE}/admin/announcements`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ title: annTitle.trim(), content: annContent.trim(), kind: annKind }),
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) { setAnnMsg(d.detail || '发布失败'); return }
    setAnnMsg('')
    setAnnTitle(''); setAnnContent('')
    loadAnns()
  }

  const deleteAnn = async (id: string) => {
    if (!window.confirm('确定删除该公告？')) return
    await fetch(`${API_BASE}/admin/announcements/${id}`, { method: 'DELETE', headers: headers() })
    loadAnns()
  }

  // ---- 邮箱验证码 SMTP 配置（R1' 2026-11-05：后台热配置，零服务器操作） ----
  const [smtp, setSmtp] = useState<any>(null)
  const [smtpForm, setSmtpForm] = useState({ host: '', port: 465, user: '', password: '', from_addr: '', use_ssl: true })
  const [smtpMsg, setSmtpMsg] = useState('')
  const [smtpSaving, setSmtpSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testMsg, setTestMsg] = useState('')
  const [testSending, setTestSending] = useState(false)

  const loadSmtp = () => {
    fetch(`${API_BASE}/admin/smtp-config`, { headers: headers() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          setSmtp(d)
          setSmtpForm((p) => ({
            ...p,
            host: d.host || p.host,
            port: d.port || 465,
            user: d.user || '',
            from_addr: d.from_addr || '',
            use_ssl: d.use_ssl !== false,
            // 密码不回传，输入框始终空 = 保持原密码
          }))
        }
      })
      .catch(() => {})
  }
  useEffect(() => { loadSmtp() }, [])

  const saveSmtp = async () => {
    setSmtpSaving(true); setSmtpMsg('')
    const res = await fetch(`${API_BASE}/admin/smtp-config`, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify(smtpForm),
    })
    const d = await safeJson(res)
    if (!res.ok) { setSmtpMsg(d?.detail || '保存失败') } else { setSmtpMsg('已保存，立即生效'); loadSmtp() }
    setSmtpSaving(false)
  }

  const sendSmtpTest = async () => {
    if (!testTo.trim()) { setTestMsg('请填写测试收件邮箱'); return }
    setTestSending(true); setTestMsg('')
    const res = await fetch(`${API_BASE}/admin/smtp-config/test`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ email: testTo.trim() }),
    })
    const d = await safeJson(res)
    if (!res.ok) { setTestMsg(d?.detail || '发送失败') } else { setTestMsg(d?.message || '已发送') }
    setTestSending(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 更新公告（2026-10-31）：发布/列表/删除；部署与 Agent 版本更新会自动发布 */}
      <Card>
        <CardHeader title="更新公告" />
        <div style={{ padding: '4px 20px', fontSize: 11, color: 'var(--text-muted)' }}>
          网站部署更新与本地 Agent 新版本发布会自动生成公告；此处可手动补充发布。
        </div>
        <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 8, borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={annKind} onChange={(e) => setAnnKind(e.target.value)} style={select}>
              <option value="site">平台更新</option>
              <option value="agent">Agent 更新</option>
            </select>
            <input value={annTitle} onChange={(e) => setAnnTitle(e.target.value)} maxLength={100}
              placeholder="公告标题" style={{ ...input, flex: 1 }} />
          </div>
          <textarea value={annContent} onChange={(e) => setAnnContent(e.target.value)} maxLength={2000} rows={2}
            placeholder="公告内容" style={{ ...input, width: '100%', fontFamily: 'inherit', resize: 'vertical' }} />
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button onClick={publishAnn}
              style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13 }}>
              发布公告
            </button>
            {annMsg && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{annMsg}</span>}
          </div>
        </div>
        <div style={{ maxHeight: 260, overflowY: 'auto' }}>
          {anns.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>暂无公告</div>
          ) : anns.map((a) => (
            <div key={a.id} style={{ ...row, alignItems: 'center' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ ...label, fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</div>
                <div style={hint}>{a.kind === 'agent' ? 'Agent 更新' : '平台更新'} · {a.created_at?.slice(0, 16)}</div>
              </div>
              <button onClick={() => deleteAnn(a.id)} title="删除" aria-label="删除"
                style={{ fontSize: 12, padding: '3px 10px', color: 'var(--danger)', border: '1px solid var(--danger)', background: 'none', borderRadius: 4, cursor: 'pointer', flexShrink: 0 }}>
                删除
              </button>
            </div>
          ))}
        </div>
      </Card>
      {/* 邮箱验证码登录（R1' 2026-11-05）：SMTP 后台热配置——粘贴邮箱+授权码即生效，
          零服务器操作；授权码加密存储、GET 永不回传；测试发送 60s 冷却 */}
      <Card>
        <CardHeader title="邮箱验证码登录" />
        <div style={{ padding: '4px 20px 10px', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.7 }}>
          用户输自己邮箱收验证码登录（未注册自动注册）。此处配置平台发件邮箱：163/QQ 邮箱在网页开启 SMTP 服务后获得「授权码」
          （mail.163.com → 设置 → POP3/SMTP/IMAP；授权码 ≠ 登录密码）。
          {smtp && !smtp.configured && <span style={{ color: 'var(--warning)' }}> 当前未配置，验证码登录返回 503，密码登录不受影响。</span>}
          {smtp && smtp.configured && <span style={{ color: 'var(--success)' }}> 当前已配置（{smtp.user}）。</span>}
        </div>
        {smtp && smtp.env_override && (
          <div style={{ margin: '0 20px 10px', padding: '8px 12px', borderRadius: 6, background: 'var(--warning-soft)', border: '1px solid var(--warning)', fontSize: 12, color: 'var(--warning)' }}>
            服务器环境变量 SMTP_HOST 已设置（env 优先于本页），表单仅供查看。
          </div>
        )}
        {smtp && smtp.configured && !smtp.encryption_enabled && (
          <div style={{ margin: '0 20px 10px', padding: '8px 12px', borderRadius: 6, background: 'var(--warning-soft)', border: '1px solid var(--warning)', fontSize: 12, color: 'var(--warning)' }}>
            提示：服务器未配置 ENCRYPTION_PASSWORD，授权码将以明文存储于服务器数据文件（不影响功能；建议后续在 .env 补配以加密落盘）。
          </div>
        )}
        <div style={{ padding: '10px 20px', display: 'flex', flexDirection: 'column', gap: 8, borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={smtpForm.host} onChange={(e) => setSmtpForm((p) => ({ ...p, host: e.target.value }))}
              placeholder="发信服务器（如 smtp.163.com）" style={{ ...input, flex: 1, minWidth: 180 }} />
            <input type="number" value={smtpForm.port} onChange={(e) => setSmtpForm((p) => ({ ...p, port: Number(e.target.value) }))}
              placeholder="端口 465" style={{ ...input, maxWidth: 90 }} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input type="checkbox" checked={smtpForm.use_ssl} onChange={(e) => setSmtpForm((p) => ({ ...p, use_ssl: e.target.checked }))} />
              SSL
            </label>
          </div>
          <input value={smtpForm.user} onChange={(e) => setSmtpForm((p) => ({ ...p, user: e.target.value }))}
            placeholder="发件邮箱（如 chengjie2017020@163.com）" style={input} />
          <input type="password" value={smtpForm.password} onChange={(e) => setSmtpForm((p) => ({ ...p, password: e.target.value }))}
            placeholder={smtp?.has_password ? '授权码（留空 = 保持原密码不变）' : '授权码（SMTP 授权码，非登录密码）'}
            autoComplete="new-password" style={input} />
          <input value={smtpForm.from_addr} onChange={(e) => setSmtpForm((p) => ({ ...p, from_addr: e.target.value }))}
            placeholder='发件人显示名（如 小元AI <noreply@你的域名>，可留空）' style={input} />
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button onClick={saveSmtp} disabled={smtpSaving}
              style={{ padding: '7px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13, opacity: smtpSaving ? 0.6 : 1 }}>
              保存配置
            </button>
            {smtpMsg && <span style={{ fontSize: 12, color: smtpMsg.includes('已保存') ? 'var(--accent)' : 'var(--danger)' }}>{smtpMsg}</span>}
          </div>
        </div>
        <div style={{ padding: '12px 20px', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input value={testTo} onChange={(e) => setTestTo(e.target.value)}
            placeholder="测试收件邮箱" style={{ ...input, minWidth: 180 }} />
          <button onClick={sendSmtpTest} disabled={testSending}
            style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)', background: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12.5, opacity: testSending ? 0.6 : 1 }}>
            发送测试邮件
          </button>
          {testMsg && <span style={{ fontSize: 12, color: testMsg.includes('失败') || testMsg.includes('频繁') ? 'var(--danger)' : 'var(--success)' }}>{testMsg}</span>}
        </div>
      </Card>

      {/* 2026-10-19 清理：日志级别/错误通知/自动收起侧栏三个开关全项目无
          消费方（仅写 localStorage）——移除误导性控件 */}
      <Card>
        <CardHeader title="助手设定" />
        <div style={{ padding: '4px 20px', fontSize: 11, color: 'var(--text-muted)' }}>模型的自我认知与聊天提示词——问它「你是什么模型/能做什么」时按这里的设定回答</div>
        {PROMPT_FIELDS.map((f) => (
          <div key={f.key} style={{ ...row, flexDirection: 'column', alignItems: 'stretch' }}>
            <div>
              <div style={label}>{f.label}</div>
              <div style={hint}>{f.hint}</div>
            </div>
            <textarea value={cfg[f.key] ?? ''} rows={f.rows}
              onChange={(e) => setVal(f.key, e.target.value)}
              style={{ ...input, width: '100%', fontFamily: 'inherit', fontSize: 12, resize: 'vertical', minHeight: 60 }} />
          </div>
        ))}
        <div style={{ padding: '14px 20px', display: 'flex', gap: 12, alignItems: 'center' }}>
          <button onClick={handleSaveCfg} disabled={saving}
            style={{ padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13, opacity: saving ? 0.6 : 1 }}>
            保存设定
          </button>
          {msg && <span style={{ fontSize: 12, color: msg.includes('已保存') ? 'var(--accent)' : 'var(--danger)' }}>{msg}</span>}
        </div>
      </Card>

      <Card>
        <CardHeader title="系统参数" />
        <div style={{ padding: '4px 20px', fontSize: 11, color: 'var(--text-muted)' }}>记忆机制 / 推理强度 / 配额开关（保存后立即生效，无需重启；环境变量已设置的项优先于本页，以黄条标注）</div>
        {PARAM_FIELDS.map((f) => (
          <div key={f.key} style={row}>
            <div>
              <div style={label}>{f.label}</div>
              <div style={hint}>{f.hint}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {f.kind === 'bool' ? (
                <Toggle checked={!!cfg[f.key]} onChange={(v) => setVal(f.key, v)} />
              ) : f.kind === 'select' ? (
                <select value={cfg[f.key] ?? ''} onChange={(e) => setVal(f.key, e.target.value)} style={select}>
                  {(f.choices || []).map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              ) : (
                <input type="number" step={f.step ?? 1} value={cfg[f.key] ?? ''} onChange={(e) => setVal(f.key, Number(e.target.value))} style={{ ...input, maxWidth: 120 }} />
              )}
            </div>
          </div>
        ))}
        {effective && (
          <div style={{ padding: '14px 20px', fontSize: 12, color: 'var(--text-muted)' }}>
            <div style={{ marginBottom: 6, fontWeight: 600, color: 'var(--text-secondary)' }}>运行实况（只读）</div>
            <div>Agent 模型分配：{Object.entries(effective.agent_models || {}).map(([k, v]) => `${k}=${v}`).join('，')}</div>
            <div style={{ marginTop: 4 }}>已注册工具：{effective.tool_count} 个（{Object.entries(effective.tool_categories || {}).map(([k, v]) => `${k} ${v}`).join(' / ')}）</div>
          </div>
        )}
        <div style={{ padding: '14px 20px' }}>
          <button onClick={handleSaveCfg} disabled={saving}
            style={{ padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13, opacity: saving ? 0.6 : 1 }}>
            保存参数
          </button>
        </div>
      </Card>

      <Card>
        <CardHeader title="关于" />
        <div style={row}>
          <div style={label}>版本</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>小元AI v2.0</div>
        </div>
        <div style={row}>
          <div style={label}>前端</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>React 19 + TypeScript + Vite</div>
        </div>
        <div style={row}>
          <div style={label}>后端</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>FastAPI + LangGraph + MySQL + Redis</div>
        </div>
      </Card>
    </div>
  )
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      style={{
        width: 40, height: 22, borderRadius: 11,
        background: checked ? 'var(--accent)' : 'var(--text-muted)',
        cursor: 'pointer', position: 'relative',
        transition: 'background 0.2s',
        flexShrink: 0,
      }}
    >
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#fff',
        position: 'absolute', top: 2,
        left: checked ? 20 : 2,
        transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </div>
  )
}
