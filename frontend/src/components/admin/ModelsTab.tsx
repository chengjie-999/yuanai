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
  const [newId, setNewId] = useState('')
  const [newProvider, setNewProvider] = useState('Custom'); const [newKey, setNewKey] = useState('')
  const [agentModels, setAgentModels] = useState<Record<string, string>>({})
  const [savingAssign, setSavingAssign] = useState(false)
  const [assignMsg, setAssignMsg] = useState('')
  // 自动检查更新：升级清单 + 语音配置
  const [upgradePlan, setUpgradePlan] = useState<{ model_upgrades: any[]; voice_upgrades: any[]; available: any[] } | null>(null)
  const [checking, setChecking] = useState(false)
  const [upgrading, setUpgrading] = useState(false)
  const [upgradeMsg, setUpgradeMsg] = useState('')
  const [voiceConfig, setVoiceConfig] = useState<Record<string, string>>({})
  const [savingVoice, setSavingVoice] = useState(false)
  const [voiceMsg, setVoiceMsg] = useState('')

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

  const handleCheckUpdates = async () => {
    setChecking(true); setUpgradeMsg(''); setUpgradePlan(null)
    try {
      const res = await fetch(`${API_BASE}/admin/models/upgrade-plan`, { headers: headers() })
      const d = await safeJson(res)
      if (!res.ok) { setUpgradeMsg(d?.detail || '检查失败') } else { setUpgradePlan(d) }
    } catch { setUpgradeMsg('检查失败（网络异常）') }
    setChecking(false)
  }

  const handleApplyUpgrades = async () => {
    setUpgrading(true); setUpgradeMsg('')
    try {
      const res = await fetch(`${API_BASE}/admin/models/upgrade`, { method: 'POST', headers: headers() })
      const d = await safeJson(res)
      if (!res.ok) { setUpgradeMsg(d?.detail || '升级失败') } else {
        const n = (d?.model_upgrades?.length || 0) + (d?.voice_upgrades?.length || 0)
        setUpgradeMsg(n ? `已自动更换 ${n} 项，立即生效` : '没有需要更换的模型')
        loadModels(); loadAgentModels(); handleCheckUpdates()
      }
    } catch { setUpgradeMsg('升级失败（网络异常）') }
    setUpgrading(false)
  }

  const handleSaveVoice = async () => {
    setSavingVoice(true); setVoiceMsg('')
    const res = await fetch(`${API_BASE}/admin/voice-config`, { method: 'PUT', headers: headers(), body: JSON.stringify({ voice_config: voiceConfig }) })
    const d = await safeJson(res)
    if (!res.ok) { setVoiceMsg(d?.detail || '保存失败') } else { setVoiceMsg('已保存，立即生效') }
    setSavingVoice(false)
  }

  const loadVoiceConfig = () => {
    fetch(`${API_BASE}/admin/voice-config`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(); return r.json() })
      .then((data) => { if (data?.voice_config && typeof data.voice_config === 'object') setVoiceConfig(data.voice_config) })
      .catch(() => {})
  }
  useEffect(() => { loadVoiceConfig() }, [])

  const handleAdd = async () => {
    if (!newId.trim()) return
    setError('')
    // label 用模型 ID 本身（显示名无意义）
    const res = await fetch(`${API_BASE}/admin/models`, { method: 'POST', headers: headers(), body: JSON.stringify({ model_id: newId.trim(), label: newId.trim(), provider: newProvider.trim() || 'Custom' }) })
    if (!res.ok) { const d = await safeJson(res); setError(d?.detail || '添加失败'); return }
    if (newKey.trim()) { await fetch(`${API_BASE}/admin/apikeys`, { method: 'POST', headers: headers(), body: JSON.stringify({ provider: newProvider.trim() || 'Custom', key: newKey.trim() }) }) }
    setShowModal(false); setNewId(''); setNewProvider('Custom'); setNewKey('')
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
                {['模型 ID', '供应商', ''].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)' }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {entries.map(([id, info]) => {
                  if (!info || typeof info !== 'object') return null
                  return (
                    <tr key={id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                      <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 12, color: 'var(--text-primary)' }}>{id}</td>
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
                        if (!info || typeof info !== 'object') return null
                        return <option key={id} value={id}>{id}</option>
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
            {assignMsg && <span style={{ fontSize: 12, color: assignMsg.includes('已保存') ? 'var(--accent)' : 'var(--danger)' }}>{assignMsg}</span>}
          </div>
        </Card>
      )}
      {!loading && (
        <Card>
          <CardHeader title="自动检查更新" action={<button onClick={handleCheckUpdates} disabled={checking} title="检查模型更新" aria-label="检查模型更新" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)', fontWeight: 500, opacity: checking ? 0.6 : 1 }}>{checking ? '检查中…' : '检查更新'}</button>} />
          <div style={{ padding: '0 14px 4px', fontSize: 12, color: 'var(--text-muted)' }}>对照升级知识表检查在用模型与语音模型，确认后自动添加新模型、切换分配、移除旧模型</div>
          {upgradeMsg && <div style={{ padding: '0 14px 8px', fontSize: 12, color: upgradeMsg.includes('已自动') || upgradeMsg.includes('没有') ? 'var(--accent)' : 'var(--danger)' }}>{upgradeMsg}</div>}
          {upgradePlan && (upgradePlan.model_upgrades.length > 0 || upgradePlan.voice_upgrades.length > 0 || upgradePlan.available.length > 0) ? (
            <div style={{ padding: '8px 14px 12px' }}>
              {[...upgradePlan.model_upgrades, ...upgradePlan.voice_upgrades].map((u, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border-light)', fontSize: 13 }}>
                  <span style={{ color: 'var(--danger)', fontFamily: 'monospace', fontSize: 12 }}>{u.old}</span>
                  <span style={{ color: 'var(--text-muted)' }}>→</span>
                  <span style={{ color: 'var(--accent)', fontFamily: 'monospace', fontSize: 12 }}>{u.new}</span>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{u.label}</span>
                  {(u.used_by?.length > 0) && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>使用处：{u.used_by.join('、')}</span>}
                </div>
              ))}
              {upgradePlan.available.length > 0 && (
                <div style={{ padding: '8px 0', fontSize: 12, color: 'var(--text-secondary)' }}>
                  可添加的新模型（需先在火山/DeepSeek 控制台开通授权）：
                  {upgradePlan.available.map((a) => <span key={a.model_id} style={{ fontFamily: 'monospace', fontSize: 11, marginLeft: 8, color: 'var(--text-muted)' }}>{a.model_id}</span>)}
                </div>
              )}
              <div style={{ paddingTop: 10 }}>
                <button onClick={handleApplyUpgrades} disabled={upgrading}
                  style={{ ...btnPrimary, opacity: upgrading ? 0.6 : 1, background: 'var(--accent)' }}>
                  {upgrading ? '更换中…' : '确认自动更换'}
                </button>
              </div>
            </div>
          ) : upgradePlan ? (
            <div style={{ padding: '8px 14px 14px', fontSize: 12, color: 'var(--text-secondary)' }}>在用模型均为最新，无需更换。</div>
          ) : null}
        </Card>
      )}
      {!loading && (
        <Card>
          <CardHeader title="语音配置" />
          <div style={{ padding: '0 14px 4px', fontSize: 12, color: 'var(--text-muted)' }}>语音合成模型/音色/资源（火山引擎控制台开通后填新值，保存立即生效；音色须与合成模型版本匹配）</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <tbody>
              {([
                ['tts_model', '合成模型（X-Api-Resource-Id）'],
                ['tts_voice', '气泡朗读默认音色'],
                ['tts_voice_bot', '通话机器人音色'],
                ['asr_resource', 'ASR 资源 ID'],
                ['tts_resource', 'TTS 双向通道资源'],
              ] as const).map(([key, label]) => (
                <tr key={key} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{label}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <input value={voiceConfig[key] || ''} onChange={(e) => setVoiceConfig((p) => ({ ...p, [key]: e.target.value }))}
                      style={{ ...inputStyle, width: '100%', maxWidth: 420, fontFamily: 'monospace', fontSize: 12 }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
            <button onClick={handleSaveVoice} disabled={savingVoice} style={{ ...btnPrimary, opacity: savingVoice ? 0.6 : 1 }}>保存语音配置</button>
            {voiceMsg && <span style={{ fontSize: 12, color: voiceMsg.includes('已保存') ? 'var(--accent)' : 'var(--danger)' }}>{voiceMsg}</span>}
          </div>
        </Card>
      )}
      {showModal && (
        <div onClick={() => setShowModal(false)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-primary)', borderRadius: 12, padding: 24, minWidth: 380, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>添加模型</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <input value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="模型 ID (如 doubao-seed-2-1-lite-260915)" style={{ ...inputStyle, fontFamily: 'monospace' }} />
              <input value={newProvider} onChange={(e) => setNewProvider(e.target.value)} placeholder="供应商 (如 Doubao/DeepSeek)" style={inputStyle} />
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
