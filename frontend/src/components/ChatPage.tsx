import { useState, useRef, useEffect, useCallback } from 'react'
import { streamChat, createSession, listSessions, deleteSession, loadMessages, saveMessages } from '../api'
import type { ChatMessage } from '../types'
import ToolCallCard from './ToolCallCard'
import MarkdownContent from './MarkdownContent'

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

function LoadingDots() {
  const [dots, setDots] = useState('')
  useEffect(() => {
    const t = setInterval(() => setDots((p) => (p.length >= 3 ? '' : p + '.')), 400)
    return () => clearInterval(t)
  }, [])
  return (
    <span style={{ color: '#999', fontStyle: 'italic', fontSize: 14 }}>
      正在输入<span style={{ letterSpacing: 1 }}>{dots}</span>
    </span>
  )
}

type SessionInfo = { session_id: string; title: string; update_time: string }

const MODELS = [
  { value: 'doubao-seed-2-0-pro-260215', label: '豆包 Pro', provider: 'Doubao' },
  { value: 'doubao-seed-2-0-lite-260215', label: '豆包 Lite', provider: 'Doubao' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash', provider: 'DeepSeek' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro', provider: 'DeepSeek' },
]

function ModelSelector({ model, onChange }: { model: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const [upward, setUpward] = useState(false)
  const current = MODELS.find((m) => m.value === model) || MODELS[0]
  const ref = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const toggle = () => {
    if (!open) {
      setOpen(true)
      setTimeout(() => {
        if (menuRef.current && ref.current) {
          const rect = ref.current.getBoundingClientRect()
          const spaceBelow = window.innerHeight - rect.bottom - 8
          setUpward(spaceBelow < 240)
        }
      }, 0)
    } else {
      setOpen(false)
    }
  }

  const provider = current.provider
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={toggle}
        style={{
          padding: '6px 12px',
          borderRadius: 8,
          border: '1px solid #e5e5e5',
          background: '#fff',
          cursor: 'pointer',
          fontSize: 13,
          color: '#333',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          transition: 'border-color 0.15s',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#bbb')}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#e5e5e5')}
      >
        <span style={{
          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
          background: provider === 'Doubao' ? '#10a37f' : '#6366f1',
        }} />
        <span style={{ fontSize: 13 }}>{current.label}</span>
        <span style={{ fontSize: 9, color: '#bbb', marginLeft: 2 }}>▼</span>
      </button>
      {open && (
        <div ref={menuRef} style={{
          position: 'absolute',
          [upward ? 'bottom' : 'top']: '100%',
          [upward ? 'marginBottom' : 'marginTop']: 4,
          left: 0,
          background: '#fff',
          borderRadius: 10,
          border: '1px solid #e5e5e5',
          boxShadow: '0 4px 24px rgba(0,0,0,0.1)',
          padding: 6,
          zIndex: 100,
          minWidth: 210,
        }}>
          {['Doubao', 'DeepSeek'].map((p) => (
            <div key={p}>
              <div style={{
                fontSize: 11, fontWeight: 600, color: '#999',
                padding: '4px 8px', marginTop: 4, letterSpacing: 0.5,
                textTransform: 'uppercase',
              }}>
                {p}
              </div>
              {MODELS.filter((m) => m.provider === p).map((m) => (
                <div
                  key={m.value}
                  onClick={() => { onChange(m.value); setOpen(false) }}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    background: model === m.value ? '#f5f5f5' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    transition: 'background 0.1s',
                  }}
                  onMouseEnter={(e) => { if (model !== m.value) e.currentTarget.style.background = '#fafafa' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = model === m.value ? '#f5f5f5' : 'transparent' }}
                >
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: p === 'Doubao' ? '#10a37f' : '#6366f1',
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, color: '#333' }}>{m.label}</div>
                  </div>
                  {model === m.value && (
                    <span style={{ color: '#10a37f', fontSize: 14 }}>✓</span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const SUGGESTIONS = [
  '帮我查询今天的天气',
  '帮我计算 1234 × 5678',
  '请介绍一下你自己',
  '帮我分析一段数据',
]

export default function ChatPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSid, setCurrentSid] = useState<string>('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState('doubao-seed-2-0-pro-260215')
  const [quickInput, setQuickInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const messagesRef = useRef(messages)
  messagesRef.current = messages

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
      setMessages(history.map((m: any) => ({ role: m.role, content: m.content, toolCalls: [] })))
    }
  }

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    await deleteSession(sid)
    if (currentSid === sid) { setCurrentSid(''); setMessages([]) }
    refreshSessions()
  }

  const handleSend = () => {
    if (!input.trim() || loading || !currentSid) return
    const userMsg: ChatMessage = { role: 'user', content: input }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    const history = messagesRef.current.map((m) => ({ role: m.role, content: m.content }))
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', toolCalls: [] }
    setMessages((prev) => [...prev, assistantMsg])
    streamChat(
      { model, temperature: 0.7, prompt: input, history, system_prompt: '你是一个能调用工具的助手' },
      (event) => {
        if (event.type === 'token') {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data }; return last })
        } else if (event.type === 'tool_start') {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[i] = { ...last[i], toolCalls: [...calls] } }; return last })
        } else if (event.type === 'tool_end') {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].toolCalls = (last[i].toolCalls || []).map((c: any) => c.name === event.data.name ? { ...c, status: 'done' as const } : c) }; return last })
        } else if (event.type === 'error') {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: `❌ ${event.data}` }; return last }); setLoading(false)
        }
      },
      (error) => { setMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: `❌ ${error}` }; return last }); setLoading(false) },
      () => {
        setLoading(false)
        const msgs = messagesRef.current.map((m) => ({ role: m.role, content: m.content }))
        saveMessages(currentSid, msgs)
        refreshSessions()
      },
    )
  }

  const sendWithNewSession = async (text: string) => {
    const sid = await createSession()
    setCurrentSid(sid)
    refreshSessions()
    setInput(text)
    setQuickInput('')
    setTimeout(() => {
      setMessages([{ role: 'user', content: text }])
      setLoading(true)
      setMessages((prev) => [...prev, { role: 'assistant', content: '', toolCalls: [] }])
      streamChat(
        { model, temperature: 0.7, prompt: text, history: [], system_prompt: '你是一个能调用工具的助手' },
        (event) => {
          if (event.type === 'token') { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data }; return last }) }
          else if (event.type === 'tool_start') { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[i] = { ...last[i], toolCalls: [...calls] } }; return last }) }
          else if (event.type === 'tool_end') { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].toolCalls = (last[i].toolCalls || []).map((c: any) => c.name === event.data.name ? { ...c, status: 'done' as const } : c) }; return last }) }
          else if (event.type === 'error') { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: `❌ ${event.data}` }; return last }); setLoading(false) }
        },
        (error) => { setMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: `❌ ${error}` }; return last }); setLoading(false) },
        () => { setLoading(false); const msgs = messagesRef.current.map((m) => ({ role: m.role, content: m.content })); saveMessages(sid, msgs); refreshSessions() },
      )
    }, 100)
  }

  return (
    <div style={{ height: '100%', display: 'flex' }}>
      {/* Sidebar */}
      <div style={{
        width: sidebarOpen ? 260 : 0,
        overflow: 'hidden',
        background: '#f7f7f8',
        borderRight: '1px solid #e5e5e5',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        transition: 'width 0.2s',
      }}>
        <div style={{ padding: 12, flexShrink: 0 }}>
          <button
            onClick={handleNewSession}
            style={{
              width: '100%',
              padding: '10px 0',
              borderRadius: 8,
              border: '1px solid #d0d0d0',
              background: '#fff',
              cursor: 'pointer',
              fontSize: 14,
              color: '#333',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#999')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#d0d0d0')}
          >
            + 新对话
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '0 8px' }}>
          {sessions.map((s) => (
            <div
              key={s.session_id}
              onClick={() => handleSelectSession(s.session_id)}
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                cursor: 'pointer',
                marginBottom: 2,
                background: currentSid === s.session_id ? '#e8e8ea' : 'transparent',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: 14,
                color: '#333',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => { if (currentSid !== s.session_id) e.currentTarget.style.background = '#f0f0f0' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = currentSid === s.session_id ? '#e8e8ea' : 'transparent' }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                {s.title}
              </span>
              <span
                onClick={(e) => handleDeleteSession(e, s.session_id)}
                style={{
                  color: '#bbb', cursor: 'pointer', padding: '2px 4px', fontSize: 13, flexShrink: 0,
                  opacity: 0.3, transition: 'opacity 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.3')}
              >✕</span>
            </div>
          ))}
        </div>
        <div style={{ padding: '8px 12px', borderTop: '1px solid #e5e5e5', flexShrink: 0 }}>
          <button
            onClick={() => setSidebarOpen(false)}
            style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 13, padding: 0 }}
          >
            ◀ 收起
          </button>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {!currentSid ? (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '40px 20px',
          }}>
            <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.8 }}>💬</div>
            <h1 style={{
              fontSize: 22, fontWeight: 600, color: '#333', marginBottom: 32,
              letterSpacing: -0.5,
            }}>
              小元AI
            </h1>

            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                style={{
                  background: 'none', border: 'none', color: '#999', cursor: 'pointer',
                  fontSize: 13, marginBottom: 24, padding: 0,
                }}
              >
                ▶ 展开侧栏
              </button>
            )}

            <div style={{ maxWidth: 560, width: '100%', marginBottom: 12 }}>
              <input
                value={quickInput}
                onChange={(e) => setQuickInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && quickInput.trim()) sendWithNewSession(quickInput.trim()) }}
                placeholder="输入消息，开始对话..."
                style={{
                  width: '100%',
                  padding: '14px 18px',
                  borderRadius: 12,
                  border: '1px solid #ddd',
                  fontSize: 15,
                  outline: 'none',
                  transition: 'border-color 0.15s',
                  boxSizing: 'border-box',
                }}
                onFocus={(e) => (e.target.style.borderColor = '#1976d2')}
                onBlur={(e) => (e.target.style.borderColor = '#ddd')}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <ModelSelector model={model} onChange={setModel} />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 500 }}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendWithNewSession(s)}
                  style={{
                    padding: '8px 18px',
                    borderRadius: 20,
                    border: '1px solid #e0e0e0',
                    background: '#fff',
                    cursor: 'pointer',
                    fontSize: 13,
                    color: '#555',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1976d2'; e.currentTarget.style.color = '#1976d2' }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e0e0e0'; e.currentTarget.style.color = '#555' }}
                >
                  {s}
                </button>
              ))}
            </div>

            {sessions.length > 0 && (
              <div style={{ marginTop: 40, width: '100%', maxWidth: 560 }}>
                <div style={{ fontSize: 13, color: '#999', marginBottom: 8, paddingLeft: 4 }}>最近对话</div>
                {sessions.slice(0, 5).map((s) => (
                  <div
                    key={s.session_id}
                    onClick={() => handleSelectSession(s.session_id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      fontSize: 14,
                      color: '#333',
                      marginBottom: 1,
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = '#f5f5f5' }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  >
                    {s.title}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div style={{
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
                  const prev = messages[i - 1]
                  const sameAsPrev = prev && prev.role === msg.role
                  return (
                    <div key={i} style={{
                      marginBottom: sameAsPrev ? 2 : 18,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}>
                      {!sameAsPrev && (
                        <div style={{
                          fontSize: 12,
                          color: '#999',
                          marginBottom: 6,
                          marginLeft: msg.role === 'user' ? 0 : 4,
                          marginRight: msg.role === 'user' ? 4 : 0,
                          fontWeight: 500,
                        }}>
                          {msg.role === 'user' ? '你' : 'AI'}
                        </div>
                      )}
                      <div style={{
                        padding: '10px 16px',
                        borderRadius: msg.role === 'user'
                          ? '18px 18px 4px 18px'
                          : '4px 18px 18px 18px',
                        maxWidth: '75%',
                        background: msg.role === 'user' ? '#1976d2' : '#f0f0f0',
                        color: msg.role === 'user' ? '#fff' : '#333',
                        boxShadow: msg.role === 'user'
                          ? '0 1px 3px rgba(25,118,210,0.15)'
                          : '0 1px 2px rgba(0,0,0,0.05)',
                        whiteSpace: 'pre-wrap',
                        fontSize: 14,
                        lineHeight: 1.65,
                        overflowWrap: 'break-word',
                        wordBreak: 'break-word',
                      }}>
                        {loading && isLast && msg.role === 'assistant' && !msg.content ? (
                          <LoadingDots />
                        ) : msg.role === 'user' ? (
                          msg.content
                        ) : (
                          <MarkdownContent content={msg.content} />
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

            <div style={{
              padding: '12px 24px 24px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              borderTop: '1px solid #f0f0f0',
            }}>
              <div style={{ maxWidth: 720, width: '100%', display: 'flex', gap: 8, marginBottom: 8 }}>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="输入消息..."
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '11px 16px',
                    borderRadius: 10,
                    border: '1px solid #ddd',
                    fontSize: 14,
                    outline: 'none',
                    transition: 'border-color 0.15s',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = '#1976d2')}
                  onBlur={(e) => (e.target.style.borderColor = '#ddd')}
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim() || !currentSid}
                  style={{
                    padding: '11px 22px',
                    borderRadius: 10,
                    border: 'none',
                    background: loading || !input.trim() || !currentSid ? '#ccc' : '#1976d2',
                    color: '#fff',
                    cursor: loading || !input.trim() || !currentSid ? 'not-allowed' : 'pointer',
                    fontSize: 14,
                    fontWeight: 500,
                    transition: 'background 0.15s',
                  }}
                >
                  {loading ? '...' : '发送'}
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <ModelSelector model={model} onChange={setModel} />
                <button
                  onClick={() => {
                    const s = sessions.find(s => s.session_id === currentSid)
                    downloadChat(messages, `${s?.title || 'chat'}.txt`)
                  }}
                  title="下载聊天记录"
                  style={{
                    padding: '4px 8px',
                    borderRadius: 6,
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    fontSize: 16,
                    color: '#bbb',
                    transition: 'color 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#666')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = '#bbb')}
                >📥</button>
                {!sidebarOpen && (
                  <button
                    onClick={() => setSidebarOpen(true)}
                    style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 13, padding: 0 }}
                  >▶ 侧栏</button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
