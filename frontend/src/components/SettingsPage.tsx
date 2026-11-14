import { useState, useEffect } from 'react'
import { getStoredModel, setStoredModel, fetchModels, getStoredEffort, setStoredEffort } from '../api'
import { fetchAgentModels, updateAgentModel } from '../api'
import { fetchAgentVoices, updateAgentVoice } from '../api'
import MemoryCard from './MemoryCard'
import { useAutoRead, toggleAutoRead } from '../hooks/useAutoRead'
import { useAnswerTone, toggleAnswerTone } from '../hooks/useAnswerTone'
import { useIsMobile } from '../hooks/useIsMobile'

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid var(--border-light)', gap: 16 } as const,
  label: { fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 } as const,
  hint: { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 } as const,
  input: { padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' } as const,
  select: { padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', minWidth: 180 } as const,
  btn: { padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' } as const,
}

const ROLE_LABELS: Record<string, string> = {
  orchestrator: '统筹 Agent',
  analysis: '数据分析 Agent',
  collection: '数据采集 Agent',
  automation: '自动化 Agent',
  audit: '审核 Agent',
}

const ROLE_DESC: Record<string, string> = {
  orchestrator: '意图识别、任务路由、对话管理',
  analysis: '数据统计、图表生成、分析大屏',
  collection: '网页爬取、数据抓取',
  automation: '浏览器控制、截图监控',
  audit: 'AI 内容审核与质量判定',
}

// 语音音色：消息气泡朗读时按 Agent 使用不同声音（全部本地实测有效，须配 seed-tts-2.0）
const VOICE_ROLE_LABELS: Record<string, string> = {
  orchestrator: '小元（统筹）',
  local: '小元 · 本机',
  analysis: '数据分析 Agent',
  collection: '数据采集 Agent',
  automation: '自动化 Agent',
  claude: 'Claude Code',
}

// 语音换 DeepSeek（2026-11-14）：TTS 音色仅两档
const VOICE_OPTIONS = [
  { value: 'stella', label: '海星（女声）' },
  { value: 'tide', label: '暗潮（男声）' },
]

export default function SettingsPage() {
  const isMobile = useIsMobile()
  const [chatModel, setChatModel] = useState(getStoredModel())
  const [models, setModels] = useState<Record<string, { label: string; provider: string }>>({})
  // 自动朗读开关：默认开启，与顶部栏喇叭共用 useAutoRead 同步
  const autoRead = useAutoRead()
  // 回答完成提示音（U5，默认开启）
  const answerTone = useAnswerTone()
  const [agentModels, setAgentModels] = useState<Record<string, string>>({})
  // 2026-11-14 子页面化：执行位置 / 推理强度 / 数据集（写 localStorage + 事件同步聊天页）
  const [backendLocal, setBackendLocal] = useState<'auto' | 'cloud' | 'local'>(() => {
    try { const v = localStorage.getItem('chatBackend'); return v === 'cloud' || v === 'local' ? v : 'auto' } catch { return 'auto' }
  })
  const [effortLocal, setEffortLocal] = useState<'low' | 'medium' | 'high'>(getStoredEffort())
  const [dsList, setDsList] = useState<{ id: number; name: string; row_count: number }[]>([])
  const [dsLoading, setDsLoading] = useState(false)
  const loadDs = () => {
    setDsLoading(true)
    import('../api').then(({ fetchDatasets }) => fetchDatasets()
      .then((list: any[]) => { setDsList(Array.isArray(list) ? list : []); setDsLoading(false) })
      .catch(() => setDsLoading(false)))
  }
  const [savingRole, setSavingRole] = useState('')
  // 语音音色
  const [agentVoices, setAgentVoices] = useState<Record<string, string>>({})
  const [savingVoiceRole, setSavingVoiceRole] = useState('')
  useEffect(() => {
    fetchModels().then(setModels)
    fetchAgentModels().then(setAgentModels)
    fetchAgentVoices().then(setAgentVoices)
  }, [])

  const handleRoleModel = async (role: string, modelId: string) => {
    setSavingRole(role)
    setAgentModels(prev => ({ ...prev, [role]: modelId }))
    await updateAgentModel(role, modelId)
    setSavingRole('')
  }

  const handleRoleVoice = async (role: string, voiceId: string) => {
    setSavingVoiceRole(role)
    setAgentVoices(prev => ({ ...prev, [role]: voiceId }))
    await updateAgentVoice(role, voiceId)
    setSavingVoiceRole('')
  }

  const modelOptions = Object.entries(models).map(([id, v]) => ({
    value: id,
    label: id,  // 真实模型 ID（显示名无意义）
    provider: v.provider,
  }))

  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--bg-secondary)', padding: isMobile ? '20px 16px' : '32px 24px' }}>
      <div style={{ maxWidth: 680, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>设置</h1>

        {/* ---- 模型配置 ---- */}
        <div style={C.card}>
          <div style={C.title}>模型配置 <span style={C.sub}>— 各 Agent 角色的模型分配</span></div>
          <div style={C.row}>
            <div>
              <div style={C.label}>默认对话模型</div>
              <div style={C.hint}>新对话使用的 AI 模型</div>
            </div>
            <select
              value={chatModel}
              onChange={e => { setChatModel(e.target.value); setStoredModel(e.target.value) }}
              style={C.select}
            >
              {modelOptions.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>
          {Object.entries(ROLE_LABELS).map(([role, label]) => (
            <div key={role} style={{ ...C.row, background: savingRole === role ? 'var(--accent-light)' : undefined, transition: 'background 0.3s' }}>
              <div style={{ flex: 1 }}>
                <div style={C.label}>{label}</div>
                <div style={C.hint}>{ROLE_DESC[role]}</div>
              </div>
              <select
                value={agentModels[role] || ''}
                onChange={e => handleRoleModel(role, e.target.value)}
                style={C.select}
              >
                <option value="" disabled>选择模型...</option>
                {modelOptions.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          ))}
        </div>

        {/* ---- 自动朗读（默认开启，与输入区「朗读」按钮共用 localStorage 键） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            自动朗读
            <span style={C.sub}>　AI 回复完成后自动出声（顶部栏喇叭图标与这里同步）</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none' }}>
            <div style={{ flex: 1 }}>
              <div style={C.label}>默认开启自动朗读</div>
              <div style={C.hint}>关闭后需手动点击气泡上的喇叭图标朗读；也可随时点击顶部栏喇叭快速开关</div>
            </div>
            <button onClick={() => toggleAutoRead()} role="switch" aria-checked={autoRead}
              aria-label={autoRead ? '关闭自动朗读' : '开启自动朗读'}
              style={{
                width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                position: 'relative', flexShrink: 0,
                background: autoRead ? 'var(--accent)' : 'var(--border)',
                transition: 'background 0.2s',
              }}>
              <span style={{
                position: 'absolute', top: 2, left: autoRead ? 20 : 2,
                width: 18, height: 18, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s',
              }} />
            </button>
          </div>
        </div>

        {/* ---- 执行位置（2026-11-14 子页面化：从输入区移入） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            执行位置
            <span style={C.sub}>　自动：本机优先，离线回退云端；本机：强制本机（离线报错）</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none', gap: 8 }}>
            {(['cloud', 'auto', 'local'] as const).map((b) => (
              <button key={b} onClick={() => {
                try { localStorage.setItem('chatBackend', b) } catch { /* 忽略 */ }
                setBackendLocal(b)
                window.dispatchEvent(new Event('yuan-backend-changed'))
              }}
                aria-label={b === 'cloud' ? '云端' : b === 'auto' ? '自动' : '本机'}
                style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer',
                  padding: '6px 0', fontSize: 12.5, fontWeight: 600,
                  background: backendLocal === b ? 'var(--accent-light)' : 'transparent',
                  color: backendLocal === b ? 'var(--accent)' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
                {b === 'cloud' ? '云端' : b === 'auto' ? '自动（推荐）' : '本机'}
              </button>
            ))}
          </div>
        </div>

        {/* ---- 推理强度（2026-11-14 子页面化；三档） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            推理强度
            <span style={C.sub}>　快答省时；深思适合复杂任务（仅 DeepSeek 系列生效）</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none', gap: 8 }}>
            {(['low', 'medium', 'high'] as const).map((v) => (
              <button key={v} onClick={() => {
                setStoredEffort(v)
                setEffortLocal(v)
                window.dispatchEvent(new Event('yuan-effort-changed'))
              }}
                aria-label={v === 'low' ? '快答' : v === 'medium' ? '均衡' : '深思'}
                style={{ flex: 1, border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer',
                  padding: '6px 0', fontSize: 12.5, fontWeight: 600,
                  background: effortLocal === v ? 'var(--accent-light)' : 'transparent',
                  color: effortLocal === v ? 'var(--accent)' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
                {v === 'low' ? '快答' : v === 'medium' ? '均衡' : '深思'}
              </button>
            ))}
          </div>
        </div>

        {/* ---- 数据集（2026-11-14 子页面化：历史数据集引用复制） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            数据集
            <span style={C.sub}>　点击复制引用文本，回到对话粘贴即可使用（或直接用输入框回形针上传）</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none', flexDirection: 'column', alignItems: 'stretch', gap: 6 }}>
            {dsList.length === 0 ? (
              <button onClick={loadDs}
                style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'none',
                  cursor: 'pointer', fontSize: 12.5, color: 'var(--text-secondary)', padding: '6px 0' }}>
                {dsLoading ? '加载中…' : '加载历史数据集'}
              </button>
            ) : dsList.map((ds) => (
              <button key={ds.id}
                onClick={() => {
                  const ref = ` [数据集 #${ds.id}: ${ds.name}]`
                  navigator.clipboard?.writeText(ref).catch(() => {})
                  window.alert(`已复制引用：${ref}\n\n回到对话粘贴进输入框即可。`)
                }}
                style={{ border: '1px solid var(--border-light)', borderRadius: 8, background: 'var(--bg-input)',
                  cursor: 'pointer', padding: '6px 10px', fontSize: 12.5, color: 'var(--text-primary)',
                  display: 'flex', alignItems: 'center', gap: 8, textAlign: 'left' }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ds.name}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{ds.row_count} 行</span>
              </button>
            ))}
          </div>
        </div>

        {/* ---- 回答完成提示音（U5 通用体验 2026-10-25，默认开启） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            回答完成提示音
            <span style={C.sub}>　生成结束时响一声，切走窗口也知道答完了</span>
          </div>
          <div style={{ ...C.row, borderBottom: 'none' }}>
            <div style={{ flex: 1 }}>
              <div style={C.label}>默认开启提示音</div>
              <div style={C.hint}>仅在切走窗口/浏览其他标签时提醒；关闭后完全静音</div>
            </div>
            <button onClick={() => toggleAnswerTone()} role="switch" aria-checked={answerTone}
              aria-label={answerTone ? '关闭回答完成提示音' : '开启回答完成提示音'}
              style={{
                width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                position: 'relative', flexShrink: 0,
                background: answerTone ? 'var(--accent)' : 'var(--border)',
                transition: 'background 0.2s',
              }}>
              <span style={{
                position: 'absolute', top: 2, left: answerTone ? 20 : 2,
                width: 18, height: 18, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s',
              }} />
            </button>
          </div>
        </div>

        {/* ---- 语音音色 ---- */}
        <div style={C.card}>
          <div style={C.title}>
            语音音色
            <span style={C.sub}>　消息气泡「朗读」时每个 Agent 使用的声音（通话中小元的音色在服务器 .env 配置）</span>
          </div>
          {Object.entries(VOICE_ROLE_LABELS).map(([role, label]) => (
            <div key={role} style={{ ...C.row, background: savingVoiceRole === role ? 'var(--accent-light)' : undefined, transition: 'background 0.3s' }}>
              <div style={{ flex: 1 }}>
                <div style={C.label}>{label}</div>
              </div>
              <select
                value={agentVoices[role] || ''}
                onChange={e => handleRoleVoice(role, e.target.value)}
                style={C.select}
              >
                <option value="" disabled>选择音色...</option>
                {VOICE_OPTIONS.map(v => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>
          ))}
        </div>

        {/* ---- 我的记忆（透明可编辑的长期记忆，自加载组件） ---- */}
        <MemoryCard />

        {/* ---- vault 同步说明（只读；配置在本机 Agent 托盘） ---- */}
        <div style={C.card}>
          <div style={C.title}>
            vault 同步
            <span style={C.sub}>　Obsidian ↔ 知识星球 双向同步（本机 Agent 托盘配置）</span>
          </div>
          <div style={{ ...C.row, flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              1. 本机 Agent 托盘右键 →「设置 vault 路径...」选择 Obsidian 仓库里的「知识星球」目录<br />
              2. 勾选「vault 同步」→ 重启 Agent<br />
              3. 笔记互相自动同步：vault 改动上传、网页改动落盘；双改时本地赢，云端版存为 <span style={{ fontFamily: 'monospace', fontSize: 11.5 }}>*.conflict-*.md</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              同步状态见本页知识星球页右上角徽标；配置存于本机 data/agent_config.json
            </div>
          </div>
        </div>

        {/* ---- 关于 ---- */}
        <div style={C.card}>
          <div style={C.title}>关于</div>
          <div style={C.row}><div style={C.label}>版本</div><div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>小元AI v2.0</div></div>
          <div style={{ ...C.row, borderBottom: 'none' }}>
            <div style={C.label}>技术栈</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>FastAPI + React + LangGraph + MySQL</div>
          </div>
        </div>
      </div>
    </div>
  )
}
