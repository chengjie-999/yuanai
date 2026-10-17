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
const PARAM_FIELDS: { key: string; label: string; hint: string; kind: 'number' | 'bool' | 'select' | 'text' | 'json'; choices?: string[] }[] = [
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
]

const PROMPT_FIELDS: { key: string; label: string; hint: string; rows?: number }[] = [
  { key: 'chat_system_prompt', label: '聊天系统提示词', hint: '空 = 使用前端内置默认提示词；保存后新对话生效', rows: 10 },
  { key: 'self_report_template', label: '模型自报模板', hint: '模型被问「你是什么模型」时的回答模板，{model} 占位为运行时真实模型 ID（不可造假）', rows: 3 },
  { key: 'capability_note', label: '能力说明备注', hint: '追加在系统提示词末尾的能力/边界说明', rows: 4 },
]

export default function SettingsTab() {
  const [logLevel, setLogLevel] = useState(localStorage.getItem('logLevel') || 'info')
  const [notifyError, setNotifyError] = useState(localStorage.getItem('notifyError') !== 'false')
  const [autoCollapse, setAutoCollapse] = useState(localStorage.getItem('autoCollapse') === 'true')
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

  const save = (key: string, value: string) => localStorage.setItem(key, value)

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card>
        <CardHeader title="基本设置（仅本机浏览器）" />
        <div style={row}>
          <div>
            <div style={label}>日志级别</div>
            <div style={hint}>控制前端控制台日志详细程度</div>
          </div>
          <select
            value={logLevel}
            onChange={(e) => { setLogLevel(e.target.value); save('logLevel', e.target.value) }}
            style={select}
          >
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warn">Warn</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div style={row}>
          <div>
            <div style={label}>错误通知</div>
            <div style={hint}>请求失败时在页面顶部显示通知</div>
          </div>
          <Toggle checked={notifyError} onChange={(v) => { setNotifyError(v); save('notifyError', String(v)) }} />
        </div>
        <div style={row}>
          <div>
            <div style={label}>自动收起侧栏</div>
            <div style={hint}>进入对话后自动收起工具栏侧栏</div>
          </div>
          <Toggle checked={autoCollapse} onChange={(v) => { setAutoCollapse(v); save('autoCollapse', String(v)) }} />
        </div>
      </Card>

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
          {msg && <span style={{ fontSize: 12, color: msg.includes('已保存') ? 'var(--accent)' : 'var(--danger, #d93025)' }}>{msg}</span>}
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
                <input type="number" value={cfg[f.key] ?? ''} onChange={(e) => setVal(f.key, Number(e.target.value))} style={{ ...input, maxWidth: 120 }} />
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
