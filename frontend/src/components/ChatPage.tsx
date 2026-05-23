import { useState, useRef, useEffect, useCallback } from 'react'
import { streamChat, createSession, listSessions, deleteSession, loadMessages, saveMessages, getStoredModel, setStoredModel, getToken, uploadDataset } from '../api'
import type { ChatMessage } from '../types'
import ToolCallCard from './ToolCallCard'
import MarkdownContent from './MarkdownContent'
import { ModelSelector } from './ModelSelector'

function addToken(url: string): string {
  if (url.startsWith('data:')) return url
  if (!url.startsWith('/api/v1/')) return url
  if (url.includes('?token=')) return url
  return `${url}?token=${getToken()}`
}

function stripMarkdown(text: string): string {
  return text
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`{1,3}[^`]*`{1,3}/g, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/>\s+/g, '')
    .replace(/[-*+]\s+/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function downloadChat(messages: ChatMessage[], filename: string) {
  const text = messages
    .map((m) => {
      const role = m.role === 'user' ? 'You' : 'AI'
      const content = m.role === 'assistant' ? stripMarkdown(m.content) : m.content
      return `[${role}]\n${content}\n`
    })
    .join('\n---\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function encodeMsg(m: any) {
  const meta: any = {}
  if (m.sender && m.sender !== 'orchestrator') meta.s = m.sender
  if (m.toolCalls?.length) meta.t = m.toolCalls
  const content = Object.keys(meta).length > 0
    ? `\x00META\x00${JSON.stringify(meta)}\x00${m.content || ''}`
    : (m.content || '')
  return { role: m.role, content, ...(m.images?.length ? { images: m.images } : {}) }
}

const AGENT_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  orchestrator: { label: '小元AI', color: '#1976d2', bg: '#f0f5ff' },
  analysis: { label: '数据分析 Agent', color: '#7b1fa2', bg: '#faf5ff' },
  collection: { label: '数据采集 Agent', color: '#00695c', bg: '#f0faf9' },
  automation: { label: '自动化 Agent', color: '#e65100', bg: '#fff8f0' },
}

function senderFromTool(name: string): string | null {
  if (name.startsWith('delegate_to_analysis')) return 'analysis'
  if (name.startsWith('delegate_to_collection')) return 'collection'
  if (name.startsWith('delegate_to_automation')) return 'automation'
  return null
}

function LoadingDots() {
  const [dots, setDots] = useState('')
  useEffect(() => {
    const t = setInterval(() => setDots((p) => (p.length >= 3 ? '' : p + '.')), 400)
    return () => clearInterval(t)
  }, [])
  return (
    <span style={{ color: '#999', fontStyle: 'italic', fontSize: 14 }}>
      正在思考<span style={{ letterSpacing: 1 }}>{dots}</span>
    </span>
  )
}

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string }

const SUGGESTIONS: { text: string; desc: string }[] = [
  { text: '帮我分析一下数据集', desc: '数据分析' },
  { text: '抓取这个网页的内容', desc: '数据采集' },
  { text: '帮我审核小猿众包题目', desc: '自动化' },
  { text: '列出当前所有数据集', desc: '数据管理' },
]

function timeAgo(dateStr: string): string {
  const now = new Date()
  const d = new Date(dateStr)
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffDays < 1) {
    if (d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) return '今天'
    return '昨天'
  }
  if (diffDays < 2) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}月前`
  return `${Math.floor(diffDays / 365)}年前`
}

function groupSessions(sessions: SessionInfo[]): { label: string; items: SessionInfo[] }[] {
  const groups: { label: string; items: SessionInfo[] }[] = []
  let currentLabel = ''
  let currentGroup: SessionInfo[] = []

  for (const s of sessions) {
    const label = timeAgo(s.create_time)
    if (label !== currentLabel) {
      if (currentGroup.length > 0) groups.push({ label: currentLabel, items: currentGroup })
      currentLabel = label
      currentGroup = []
    }
    currentGroup.push(s)
  }
  if (currentGroup.length > 0) groups.push({ label: currentLabel, items: currentGroup })
  return groups
}

export default function ChatPage({ user, focusKey = 0 }: { user?: any; focusKey?: number }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSid, setCurrentSid] = useState<string>('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState(getStoredModel)
  const [quickInput, setQuickInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [images, setImages] = useState<string[]>([])
  const [expandedImage, setExpandedImage] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const prevFocusRef = useRef(focusKey)

  const refreshSessions = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
  }, [])

  useEffect(() => { refreshSessions() }, [refreshSessions])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleNewSession = async () => {
    setCurrentSid('')
    setMessages([])
  }

  const handleSelectSession = async (sid: string) => {
    setCurrentSid(sid)
    const history = await loadMessages(sid)
    if (history.length === 0) {
      setMessages([{ role: 'assistant', content: '你好！有什么可以帮你的？' }])
    } else {
      setMessages(history.map((m: any) => {
        let sender: any = undefined
        let toolCalls: any = undefined
        let content = m.content || ''
        if (typeof content === 'string' && content.startsWith('\x00META\x00')) {
          const end = content.indexOf('\x00', 6)
          if (end > 6) {
            try { const meta = JSON.parse(content.substring(6, end)); sender = meta.s; toolCalls = meta.t; content = content.substring(end + 1) } catch {}
          }
        }
        return { role: m.role, content, images: m.images, sender, toolCalls }
      }))
    }
  }

  // 点击导航"对话"时自动跳转最近会话
  useEffect(() => {
    if (focusKey > 0 && focusKey !== prevFocusRef.current) {
      prevFocusRef.current = focusKey
      listSessions().then((list) => {
        if (list.length > 0) handleSelectSession(list[0].session_id)
      })
    }
  }, [focusKey])

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    await deleteSession(sid)
    if (currentSid === sid) { setCurrentSid(''); setMessages([]) }
    refreshSessions()
  }

  const SYSTEM_PROMPT = '你是小元AI的统筹助手，管理着数据分析、数据采集、自动化三个专业Agent团队。\n\n你可以委派的Agent：\n- delegate_to_analysis_agent：数据分析\n- delegate_to_collection_agent：数据采集\n- delegate_to_automation_agent：自动化\n\n工作原则：\n1. 判断意图，用一句话告诉用户将调用哪个Agent，然后立刻调用\n2. 子Agent返回结果后，如果结果已经清晰完整，只做简短确认如"以上是结果"，不要再复述\n3. 只有当结果需要解读、比较或给出建议时，才补充分析\n4. 用户能看到子Agent的输出，重复内容只会让对话冗余'

  const makeStreamHandlers = () => {
    let currentSender = 'orchestrator'
    const onEvent = (event: any) => {
      if (event.type === 'token') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data, sender: (last[i].sender || currentSender) as any }; return last })
      } else if (event.type === 'reasoning') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], reasoning: (last[i].reasoning || '') + event.data }; return last })
      } else if (event.type === 'tool_start') {
        const ns = senderFromTool(event.data.name)
        if (ns) { currentSender = ns; setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: ns as any, toolCalls: [{ name: event.data.name, status: 'running' as const }] }]) }
        else { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[i] = { ...last[i], toolCalls: [...calls] } }; return last }) }
      } else if (event.type === 'tool_end') {
        const isDel = !!senderFromTool(event.data.name)
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].toolCalls = (last[i].toolCalls || []).map((c: any) => c.name === event.data.name ? { ...c, status: 'done' as const, result: event.data.output || '' } : c) }; return last })
        if (isDel) { currentSender = 'orchestrator'; setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: 'orchestrator', toolCalls: [] }]) }
      } else if (event.type === 'image') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].images = [...(last[i].images || []), event.data] }; return last })
      } else if (event.type === 'progress') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0 && last[i].role === 'assistant') last[i] = { ...last[i], progress: event.data }; return last })
      } else if (event.type === 'error') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: `请求失败，请重试` }; return last }); setLoading(false)
      }
    }
    const onError = () => { setMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: '网络异常，请检查连接' }; return last }); setLoading(false) }
    return { onEvent, onError }
  }

  const handleSend = () => {
    if (!input.trim() || loading || !currentSid) return
    const sid = currentSid
    const sentImages = images.length > 0 ? [...images] : undefined
    const prevMsgs = [...messages]
    setMessages((prev) => [...prev, { role: 'user', content: input, images: sentImages }])
    setImages([]); setInput(''); setLoading(true)
    const history = prevMsgs.map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [...prev, { role: 'assistant', content: '', toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt: input, images: sentImages, history, system_prompt: SYSTEM_PROMPT },
      onEvent, onError,
      () => {
        setLoading(false)
        const msgs = messagesRef.current.map(encodeMsg)
        saveMessages(sid, msgs, input.length > 50 ? input.slice(0, 50) + '...' : input)
        refreshSessions()
      },
    )
  }

  const sendWithNewSession = async (text: string) => {
    setLoading(true)
    const sid = await createSession()
    setCurrentSid(sid); refreshSessions()
    setInput(text); setQuickInput('')
    const sentImages = [...images]; setImages([])
    setMessages([{ role: 'user', content: text, images: sentImages.length > 0 ? sentImages : undefined }])
    setMessages((prev) => [...prev, { role: 'assistant', content: '', sender: 'orchestrator', toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt: text, images: sentImages.length > 0 ? sentImages : undefined, history: [], system_prompt: SYSTEM_PROMPT },
      onEvent, onError,
      () => {
        setLoading(false)
        const msgs = messagesRef.current.map(encodeMsg)
        saveMessages(sid, msgs, text.length > 50 ? text.slice(0, 50) + '...' : text)
        refreshSessions()
      },
    )
  }

  return (
    <>
    <style>{`
      @media (max-width: 768px) {
        .chat-sidebar { position: fixed !important; z-index: 1000 !important; left: 0 !important; top: 0 !important; height: 100% !important; width: 280px !important; box-shadow: 2px 0 12px rgba(0,0,0,0.15) !important; }
        .chat-sidebar + div[style] { left: 0 !important; }
        .chat-main { padding: 16px 8px !important; }
        .chat-welcome { padding: 24px 12px !important; }
        .chat-welcome h1 { font-size: 24px !important; }
        .chat-welcome > div:last-child { max-width: 100% !important; padding: 0 12px !important; }
        .chat-msg-bubble { max-width: 85% !important; }
        .chat-input-area { padding: 8px 12px 16px !important; }
        .chat-input-inner { max-width: 100% !important; }
      }
      @media (max-width: 480px) {
        .chat-msg-bubble { max-width: 90% !important; font-size: 13px !important; }
      }
    `}</style>
    <div style={{ height: '100%', display: 'flex', position: 'relative' }}>
      {/* Sidebar */}
      <div className="chat-sidebar" style={{
        width: sidebarOpen ? 260 : 0,
        overflow: 'hidden',
        background: '#f8f9fb',
        borderRight: '1px solid #e8e8ec',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        transition: 'width 0.2s',
      }}>
        <div style={{ padding: '12px 12px 8px', flexShrink: 0 }}>
          <button onClick={handleNewSession}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 8,
              border: '1px solid #d0d0d0', background: '#fff',
              cursor: 'pointer', fontSize: 14, color: '#333',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#999')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#d0d0d0')}
          >
            + 新对话
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
          {groupSessions(sessions).map((group) => (
            <div key={group.label}>
              <div style={{ fontSize: 11, color: '#b0b8c8', padding: '12px 14px 4px', fontWeight: 600, letterSpacing: 0.5 }}>{group.label}</div>
              {group.items.map((s) => (
                <div key={s.session_id} onClick={() => handleSelectSession(s.session_id)}
                  style={{
                    padding: '9px 12px', borderRadius: 8, cursor: 'pointer', margin: '0 6px 2px',
                    background: currentSid === s.session_id ? '#eef0f5' : 'transparent',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    fontSize: 14, color: currentSid === s.session_id ? '#1a1a2e' : '#444',
                    transition: 'all 0.12s',
                  }}
                  onMouseEnter={(e) => { if (currentSid !== s.session_id) e.currentTarget.style.background = '#f0f0f4' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = currentSid === s.session_id ? '#eef0f5' : 'transparent' }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                    {s.title.startsWith('🔧') ? <>{s.title}</> : s.title}
                  </span>
                  <span onClick={(e) => handleDeleteSession(e, s.session_id)}
                    style={{ color: '#bbb', cursor: 'pointer', padding: '2px 4px', fontSize: 13, flexShrink: 0, opacity: 0, transition: 'opacity 0.12s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
                  >✕</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* 侧边栏折叠/展开按钮 */}
      <div onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'absolute', left: sidebarOpen ? 258 : 0, top: 64, zIndex: 10,
          padding: '12px 4px', borderRadius: '0 8px 8px 0',
          background: '#fff', cursor: 'pointer', fontSize: 12, color: '#999',
          border: '1px solid #e8e8ec',
          borderLeft: sidebarOpen ? 'none' : '1px solid #e8e8ec',
          boxShadow: sidebarOpen ? '1px 1px 4px rgba(0,0,0,0.04)' : '0 1px 3px rgba(0,0,0,0.06)',
          lineHeight: 1, transition: 'left 0.2s',
        }}
      >{sidebarOpen ? '◀' : '▶'}</div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {!currentSid ? (
          <div className="chat-welcome" style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '20px', minHeight: 0, overflowY: 'auto',
            background: '#fff',
            position: 'relative',
          }}>
            {/* 装饰圆点 */}
            <div style={{ position: 'absolute', width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(179,157,219,0.08) 0%, transparent 70%)', top: -80, right: -60 }} />
            <div style={{ position: 'absolute', width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(144,202,249,0.06) 0%, transparent 70%)', bottom: 40, left: -40 }} />

            <div style={{ marginTop: 'auto', marginBottom: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 560 }}>
            <div style={{ position: 'relative', width: 80, height: 80, marginBottom: 16, animation: 'float 3s ease-in-out infinite' }}>
              <svg viewBox="0 0 100 100" width={80} height={80}>
                <circle cx="50" cy="50" r="42" fill="#42a5f5" opacity="0.08" />
                <circle cx="50" cy="52" r="32" fill="#1976d2" />
                <circle cx="50" cy="52" r="27" fill="#42a5f5" />
                {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
                  <g key={i}>
                    <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#1976d2" strokeWidth="5" strokeLinecap="round" />
                    <circle cx={x} cy={y} r="6" fill="#90caf9" />
                  </g>
                ))}
                <ellipse cx="38" cy="44" rx="7" ry="8" fill="#fff" />
                <ellipse cx="38" cy="44" rx="4" ry="5" fill="#311b92" />
                <circle cx="40" cy="42" r="2" fill="#fff" opacity="0.9" />
                <path d="M53 44 Q59 38 65 44" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0">
                  <animate attributeName="opacity" values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;1;0" dur="4s" repeatCount="indefinite" />
                </path>
                <ellipse cx="59" cy="44" rx="7" ry="8" fill="#fff">
                  <animate attributeName="ry" values="8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;3;1;8" dur="4s" repeatCount="indefinite" />
                </ellipse>
                <ellipse cx="59" cy="44" rx="4" ry="5" fill="#0d47a1">
                  <animate attributeName="ry" values="5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;1.5;0.5;5" dur="4s" repeatCount="indefinite" />
                </ellipse>
                <circle cx="61" cy="42" r="2" fill="#fff" opacity="0.9">
                  <animate attributeName="opacity" values="0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0;0;0.9" dur="4s" repeatCount="indefinite" />
                </circle>
                <path d="M42 60 Q50 70 58 60" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0.85" />
                <ellipse cx="30" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
                <ellipse cx="70" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
              </svg>
            </div>
            <h1 style={{ fontSize: 26, fontWeight: 700, color: '#2c2c54', marginBottom: 4, letterSpacing: -0.5 }}>小元AI</h1>
            <p style={{ fontSize: 14, color: '#9ea7b8', marginBottom: 28, fontWeight: 400, letterSpacing: 0.3 }}>数据分析 / 数据采集 / 自动化 / 多智能体协作</p>

            <div style={{ maxWidth: 560, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
              {/* 图片预览 */}
              {images.length > 0 && (
                <div style={{ display: 'flex', gap: 6, marginBottom: 8, overflowX: 'auto' }}>
                  {images.map((img, i) => (
                    <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                      <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid #eee' }} />
                      <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                        style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: '#e53935', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                    </div>
                  ))}
                </div>
              )}
              {/* 输入框 */}
              <div style={{ border: '1px solid #e0e0e0', borderRadius: 14, background: '#fff', transition: 'box-shadow 0.2s' }}
                onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px rgba(0,0,0,0.06)'}
                onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
              >
                <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
                  <textarea value={quickInput} onChange={(e) => { setQuickInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px' }}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && quickInput.trim()) { e.preventDefault(); const v = quickInput.trim(); setQuickInput(''); sendWithNewSession(v) } }}
                    placeholder="输入消息，开始对话... (Enter 发送，Shift+Enter 换行)"
                    rows={1}
                    style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflowY: 'auto' }} />
                  <input ref={fileRef} type="file" accept="image/*,.csv,.xlsx,.xls,.json" multiple hidden
                    onChange={async (e) => {
                      const files = e.target.files
                      if (!files) return
                      for (const f of Array.from(files)) {
                        const ext = f.name.split('.').pop()?.toLowerCase()
                        if (['csv','xlsx','xls','json'].includes(ext || '')) {
                          try {
                            const result = await uploadDataset(f)
                            setQuickInput((p) => p + ` [数据集 #${result.id}: ${result.name}]`)
                          } catch { /* ignore */ }
                        } else {
                          const reader = new FileReader()
                          reader.onload = () => setImages((p) => [...p, reader.result as string])
                          reader.readAsDataURL(f)
                        }
                      }
                      e.target.value = ''
                    }}
                  />
                  <button onClick={() => fileRef.current?.click()} title="上传文件/图片"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#999', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
                  >📎</button>
                  <button onClick={() => { if (quickInput.trim()) { const v = quickInput.trim(); setQuickInput(''); sendWithNewSession(v) } }} disabled={!quickInput.trim()}
                    className="btn btn-primary"
                    style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, opacity: !quickInput.trim() ? 0.5 : 1, borderRadius: 10 }}>发送</button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px 10px' }}>
                  <ModelSelector model={model} onChange={(v) => { setModel(v); setStoredModel(v) }} />
                </div>
              </div>
            </div>
            </div>

            <div style={{ marginTop: 32, width: '100%', maxWidth: 520 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px,1fr))', gap: 10 }}>
              {SUGGESTIONS.map((s) => (
                <button key={s.text} onClick={() => sendWithNewSession(s.text)}
                  style={{
                    padding: '12px 16px', borderRadius: 12, border: '1px solid #e8e8ec',
                    background: '#fff', cursor: 'pointer', fontSize: 13, color: '#333',
                    display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1976d2'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(25,118,210,0.1)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e8e8ec'; e.currentTarget.style.boxShadow = 'none' }}
                >
                  <div style={{ fontWeight: 500, fontSize: 13 }}>{s.text}</div>
                  <div style={{ fontSize: 11, color: '#999' }}>{s.desc}</div>
                </button>
              ))}
            </div>
            </div>

            {sessions.length > 0 && (
              <div style={{ marginTop: 40, width: '100%', maxWidth: 560 }}>
                <div style={{ fontSize: 11, color: '#b0b8c8', marginBottom: 10, paddingLeft: 4, fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase' }}>最近对话</div>
                {sessions.slice(0, 5).map((s) => (
                  <div key={s.session_id} onClick={() => handleSelectSession(s.session_id)}
                    className="task-item"
                    style={{
                      padding: '10px 14px', borderRadius: 8, cursor: 'pointer', fontSize: 14,
                      color: '#444', marginBottom: 2, background: 'transparent', border: '1px solid transparent',
                    }}
                  >{s.title}</div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="chat-main" style={{
              flex: 1,
              overflowY: 'auto',
              padding: '32px 16px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}>
              <div style={{ maxWidth: 720, width: '100%' }}>
                {messages.map((msg, i) => {
                  const isLast = i === messages.length - 1
                  const isUser = msg.role === 'user'
                  const sender = !isUser ? (msg.sender || 'orchestrator') : null
                  const agent = sender ? AGENT_CONFIG[sender] : null

                  return (
                    <div key={i} style={{
                      marginBottom: 14,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: isUser ? 'flex-end' : 'flex-start',
                    }}>
                      {/* Sender label */}
                      {agent && (
                        <div style={{
                          fontSize: 12, fontWeight: 600, marginBottom: 3, marginLeft: 2,
                          color: agent.color, display: 'flex', alignItems: 'center', gap: 6,
                        }}>
                          <span style={{
                            width: 6, height: 6, borderRadius: '50%', background: agent.color,
                            display: 'inline-block', flexShrink: 0,
                          }} />
                          {agent.label}
                        </div>
                      )}
                      {isUser && (
                        <div style={{ fontSize: 11, color: '#b0b8c8', marginBottom: 3, marginRight: 4, fontWeight: 500 }}>
                          {user?.display_name || user?.username || '我'}
                        </div>
                      )}

                      <div className="chat-msg-bubble" style={{
                        padding: '10px 16px',
                        borderRadius: isUser ? '18px 18px 4px 18px' : '4px 14px 14px 14px',
                        maxWidth: '75%',
                        background: isUser ? '#1976d2' : (agent?.bg || '#f5f5f8'),
                        color: isUser ? '#fff' : '#333',
                        borderLeft: agent ? `3px solid ${agent.color}` : undefined,
                        boxShadow: isUser
                          ? '0 1px 3px rgba(25,118,210,0.15)'
                          : '0 1px 2px rgba(0,0,0,0.04)',
                        whiteSpace: 'pre-wrap',
                        fontSize: 14,
                        lineHeight: 1.65,
                        overflowWrap: 'break-word',
                        wordBreak: 'break-word',
                      }}>
                        {loading && isLast && msg.role === 'assistant' && !msg.content && (!msg.toolCalls || msg.toolCalls.length === 0) ? (
                          <LoadingDots />
                        ) : isUser ? (
                          <>
                            {msg.content}
                            {msg.images && msg.images.length > 0 && (
                              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginTop: 8 }}>
                                {msg.images.map((img, j) => (
                                  <img key={j} src={addToken(img)}
                                    onClick={() => setExpandedImage(addToken(img))}
                                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid #e0e0e0' }} />
                                ))}
                              </div>
                            )}
                          </>
                        ) : (
                          <>
                            {msg.progress && (
                              <div style={{ marginBottom: 8, padding: '6px 10px', background: '#f0f5ff', borderRadius: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#666', marginBottom: 4 }}>
                                  <span>{msg.progress.message || '处理中...'}</span>
                                  <span>{msg.progress.current}/{msg.progress.total}</span>
                                </div>
                                <div style={{ height: 4, background: '#e0e0e0', borderRadius: 2, overflow: 'hidden' }}>
                                  <div style={{ height: '100%', width: `${Math.round((msg.progress.current / Math.max(msg.progress.total, 1)) * 100)}%`, background: '#1976d2', borderRadius: 2, transition: 'width 0.3s' }} />
                                </div>
                              </div>
                            )}
                            {msg.reasoning && (
                              <details open={loading && isLast && !msg.content} style={{ marginBottom: 8 }}>
                                <summary style={{ cursor: 'pointer', fontSize: 12, color: '#888', userSelect: 'none', outline: 'none' }}>
                                  {loading && isLast && !msg.content ? '思考中...' : `思考完成${msg.reasoningTime ? ` (${msg.reasoningTime}s)` : ''}`}
                                </summary>
                                <div style={{ marginTop: 6, padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, fontSize: 12, color: '#777', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                                  {msg.reasoning}
                                </div>
                              </details>
                            )}
                            <MarkdownContent content={msg.content} />
                            {msg.images && msg.images.length > 0 && (
                              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginTop: 8 }}>
                                {msg.images.map((img, j) => (
                                  <img key={j} src={addToken(img)}
                                    onClick={() => setExpandedImage(addToken(img))}
                                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid #e0e0e0' }} />
                                ))}
                              </div>
                            )}
                          </>
                        )}
                        {msg.toolCalls?.map((tc, j) => (
                          <ToolCallCard key={j} call={tc} />
                        ))}
                      </div>
                    </div>
                  )
                })}
                <div ref={chatEndRef} />
              </div>
            </div>

            <div className="chat-input-area" style={{
              padding: '12px 24px 20px', borderTop: '1px solid #eee',
            }}>
              <div className="chat-input-inner" style={{ maxWidth: 720, margin: '0 auto', width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
                <div style={{ border: '1px solid #e0e0e0', borderRadius: 14, background: '#fff', transition: 'box-shadow 0.2s' }}
                  onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px rgba(0,0,0,0.06)'}
                  onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
                >
                  {/* 图片预览 */}
                  {images.length > 0 && (
                    <div style={{ display: 'flex', gap: 6, padding: '8px 12px 0', overflowX: 'auto' }}>
                      {images.map((img, i) => (
                        <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                          <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid #eee' }} />
                          <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                            style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: '#e53935', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* 输入行 */}
                  <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
                    <textarea value={input} onChange={(e) => { setInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px' }}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                      placeholder="输入消息... (Enter 发送，Shift+Enter 换行)" disabled={loading}
                      rows={1}
                      style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflowY: 'auto' }}
                    />
                    <input ref={fileRef} type="file" accept="image/*" multiple hidden
                      onChange={(e) => {
                        const files = e.target.files
                        if (files) {
                          Array.from(files).forEach((f) => {
                            const reader = new FileReader()
                            reader.onload = () => setImages((p) => [...p, reader.result as string])
                            reader.readAsDataURL(f)
                          })
                          e.target.value = ''
                        }
                      }}
                    />
                    <button onClick={() => fileRef.current?.click()} title="上传图片"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#999', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
                    >📎</button>
                    <button onClick={handleSend} disabled={loading || !input.trim() || !currentSid}
                      className="btn btn-primary"
                      style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, borderRadius: 10, opacity: loading || !input.trim() || !currentSid ? 0.5 : 1 }}
                    >{loading ? '...' : '发送'}</button>
                  </div>
                  {/* 底部栏 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px 10px' }}>
                    <ModelSelector model={model} onChange={(v) => { setModel(v); setStoredModel(v) }} />
                    <button onClick={() => {
                      const s = sessions.find(s => s.session_id === currentSid)
                      downloadChat(messages, `${s?.title || 'chat'}.txt`)
                    }} title="下载聊天记录" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#bbb', padding: '2px 4px', lineHeight: 1, opacity: 0.6, transition: 'opacity 0.15s' }}
                      onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={(e) => e.currentTarget.style.opacity = '0.6'}
                    >📥</button>
                    {!sidebarOpen && (
                      <button onClick={() => setSidebarOpen(true)} style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 12, padding: 0 }}>▶ 侧栏</button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
      {expandedImage && (
        <div onClick={() => setExpandedImage(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <img src={expandedImage} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 8px 40px rgba(0,0,0,0.5)' }} />
        </div>
      )}
    </div>
    </>
  )
}
