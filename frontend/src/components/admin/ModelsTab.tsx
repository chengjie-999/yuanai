import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, CardHeader, btnPrimary, inputStyle, headers, safeJson, API_BASE } from './shared'
import { XIcon } from '../icons'

// 分配键 → 中文名（后端 _AGENT_MODEL_KEYS 白名单一一对应）
const AGENT_MODEL_LABELS: Record<string, string> = {
  orchestrator: '统筹 Agent（意图识别/任务路由）',
  collection: '数据采集',
  analysis: '数据分析',
  automation: '自动化 Agent（浏览器/审核）',
  audit: '题目审核',
  memory_fold: '记忆折叠（后台异步）',
  planet_article: '星球导图文章化',
}

export default function ModelsTab() {
  const [models, setModels] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [newId, setNewId] = useState(''); const [newLabel, setNewLabel] = useState('')
  const [newProvider, setNewProvider] = useState('Custom'); const [newKey, setNewKey] = useState('')
  const [agentModels, setAgentModels] = useState<Record<string, string>>({})
  const [savingAssign, setSavingAssign] = useState(false)
  const [assignMsg, setAssignMsg] = useState('')

  const loadModels = () => {
    setError('')
    fetch(`${API_BASE}/admin/models`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { if (data && typeof data === 'object' && !Array.isArray(data)) setModels(data) })
      .catch(() => setError('加载模型配置失败'))
      .finally(() => setLoading(false))
  }
  const loadAgentModels = () => {
    fetch(`${API_BASE}/admin/agent-models`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { if (data?.agent_models && typeof data.agent_models === 'object') setAgentModels(data.agent_models) })
      .catch(() => {})
  }
  useEffect(() => { loadModels(); loadAgentModels() }, [])

  const handleSaveAssign = async () => {
    setSavingAssign(true); setAssignMsg('')
    const res = await fetch(`${API_BASE}/admin/agent-models`, { method: 'PUT', headers: headers(), body: JSON.stringify({ agent_models: agentModels }) })
    const d = await safeJson(res)
    if (!res.ok) { setAssignMsg(d?.detail || '保存失败') } else { setAssignMsg('已保存，立即生效'); loadAgentModels() }
    setSavingAssign(false)
  }

  const handleAdd = async () => {
    if (!newId.trim() || !newLabel.trim()) return
    setError('')
    const res = await fetch(`${API_BASE}/admin/models`, { method: 'POST', headers: headers(), body: JSON.stringify({ model_id: newId.trim(), label: newLabel.trim(), provider: newProvider.trim() || 'Custom' }) })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '添加失败'); return }
    if (newKey.trim()) { await fetch(`${API_BASE}/admin/apikeys`, { method: 'POST', headers: headers(), body: JSON.stringify({ provider: newProvider.trim() || 'Custom', key: newKey.trim() }) }) }
    setShowModal(false); setNewId(''); setNewLabel(''); setNewProvider('Custom'); setNewKey('')
    loadModels()
  }
  const handleDelete = async (id: string) => {
    if (!confirm(`确定删除模型 "${id}"？`)) return
    setError('')
    const res = await fetch(`${API_BASE}/admin/models`, { method: 'DELETE', headers: headers(), body: JSON.stringify({ model_id: id }) })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '删除失败'); return }
    loadModels()
  }
  const entries = Object.entries(models)

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={loadModels} />}
      {loading ? <Spinner /> : (
        <Card>
          <CardHeader title="模型配置" action={<button onClick={() => setShowModal(true)} title="添加模型" aria-label="添加模型" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)', fontWeight: 500 }}>+ 添加</button>} />
          {entries.length === 0 ? <Empty msg="暂无模型配置" /> : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
                {['用途', '模型 ID', '供应商', ''].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {entries.map(([id, info]) => {
                  if (!info || typeof info !== 'object') return null
                  const label = (info as any).label; if (!label) return null
                  const desc = id.includes('deepseek') ? (label.includes('Pro') ? '强推理' : '快速轻量') : label.includes('Pro') ? '多模态/强推理' : '轻量任务'
                  return (
                    <tr key={id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '10px 14px', fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{label}<span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>{desc}</span></td>
                      <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)' }}>{id}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{info.provider as string}</td>
                      <td style={{ padding: '10px 14px' }}>{!info.builtin && <button onClick={() => handleDelete(id)} title="删除" aria-label={`删除模型 ${id}`} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}><XIcon size={14} /></button>}</td>
                    </tr>)
                })}
              </tbody>
            </table>
          )}
        </Card>
      )}
      {!loading && (
        <Card>
          <CardHeader title="Agent 模型分配" />
          <div style={{ padding: '0 14px 4px', fontSize: 12, color: 'var(--text-muted)' }}>模型淘汰后：先添加新模型，再在此切换分配，最后删除旧模型（立即生效，无需重启）</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              {['任务', '使用模型', ''].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {Object.entries(AGENT_MODEL_LABELS).map(([key, label]) => (
                <tr key={key} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-primary)' }}>{label}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <select value={agentModels[key] || ''} onChange={(e) => setAgentModels((p) => ({ ...p, [key]: e.target.value }))}
                      style={{ ...inputStyle, minWidth: 280, padding: '6px 10px' }}>
                      {agentModels[key] && !models[agentModels[key]] && (
                        <option value={agentModels[key]}>{agentModels[key]}</option>
                      )}
                      {Object.entries(models).map(([id, info]) => {
                        if (!info || typeof info !== 'object' || !(info as any).label) return null
                        return <option key={id} value={id}>{(info as any).label}（{id}）</option>
                      })}
                    </select>
                  </td>
                  <td style={{ padding: '10px 14px' }} />
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
            <button onClick={handleSaveAssign} disabled={savingAssign} style={{ ...btnPrimary, opacity: savingAssign ? 0.6 : 1 }}>保存分配</button>
            {assignMsg && <span style={{ fontSize: 12, color: assignMsg.includes('已保存') ? 'var(--accent)' : 'var(--danger, #d93025)' }}>{assignMsg}</span>}
          </div>
        </Card>
      )}
      {showModal && (
        <div onClick={() => setShowModal(false)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-primary)', borderRadius: 12, padding: 24, minWidth: 380, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>添加模型</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="模型 ID (如 gpt-4)" style={inputStyle} />
              <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="显示名 (如 GPT-4)" style={inputStyle} />
              <input value={newProvider} onChange={(e) => setNewProvider(e.target.value)} placeholder="供应商 (如 OpenAI)" style={inputStyle} />
              <input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="API Key (可选)" style={inputStyle} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setShowModal(false)} title="取消" aria-label="取消" style={{ padding: '6px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>取消</button>
              <button onClick={handleAdd} title="确认添加" aria-label="确认添加" style={btnPrimary}>确认添加</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
