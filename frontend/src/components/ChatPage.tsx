import { useState, useRef, useEffect, useCallback } from 'react'
import { streamChat, createSession, listSessions, deleteSession, loadMessages, saveMessages, getStoredModel, setStoredModel } from '../api'
import type { ChatMessage } from '../types'
import { senderFromTool } from '../config/agents'
import { encodeMsg } from './chat/helpers'
import Sidebar from './chat/Sidebar'
import WelcomePage from './chat/WelcomePage'
import ChatView from './chat/ChatView'
import SidePanel from './chat/SidePanel'
import type { PanelType } from './chat/SidePanel'

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string }

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
  const [panel, setPanel] = useState<PanelType>(null)
  const [agentsOnline, setAgentsOnline] = useState<Record<string, boolean>>({})
  const handleModelChange = (v: string) => { setModel(v); setStoredModel(v) }
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const prevFocusRef = useRef(focusKey)

  const refreshSessions = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
  }, [])

  useEffect(() => { refreshSessions() }, [refreshSessions])

  // Poll agent status for panel availability
  useEffect(() => {
    const poll = () => {
      const token = localStorage.getItem('token')
      if (!token) return
      fetch('/api/v1/admin/agent-status', {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            const online: Record<string, boolean> = {}
            data.forEach((a: any) => {
              if (a.online && a.capabilities) {
                a.capabilities.forEach((c: string) => { online[c] = true })
              }
            })
            setAgentsOnline(online)
          }
        })
        .catch(() => {})
    }
    poll()
    const i = setInterval(poll, 15000)
    return () => clearInterval(i)
  }, [])

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
        if (ns) { currentSender = ns; setPanel(ns as PanelType); setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: ns as any, toolCalls: [{ name: event.data.name, status: 'running' as const }] }]) }
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
      <Sidebar sessions={sessions} currentSid={currentSid} sidebarOpen={sidebarOpen}
        onNewSession={handleNewSession} onSelect={handleSelectSession} onDelete={handleDeleteSession} />

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

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {!currentSid ? (
          <WelcomePage
            images={images} setImages={setImages}
            quickInput={quickInput} setQuickInput={setQuickInput}
            sendWithNewSession={sendWithNewSession}
            model={model} setModel={handleModelChange}
            sessions={sessions} onSelectSession={handleSelectSession}
          />
        ) : (
          <ChatView
            messages={messages} loading={loading} user={user}
            setExpandedImage={setExpandedImage}
            input={input} setInput={setInput} handleSend={handleSend}
            images={images} setImages={setImages}
            model={model} setModel={handleModelChange} currentSid={currentSid}
            sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
            sessions={sessions}
            panel={panel} setPanel={setPanel}
          />
        )}
      </div>

      <SidePanel panel={panel} onClose={() => setPanel(null)}
        agentOnline={panel ? !!agentsOnline[panel] : false} />

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
