import { useState, useRef, useEffect, useCallback } from 'react'
import { streamChat, createSession, listSessions, deleteSession, loadMessages, saveMessages, getStoredModel } from '../api'
import type { ChatMessage } from '../types'
import { senderFromTool } from '../config/agents'
import { encodeMsg, buildHistoryWithToolContext } from './chat/helpers'
import Sidebar from './chat/Sidebar'
import WelcomePage from './chat/WelcomePage'
import ChatView from './chat/ChatView'
import ZoomableImage from './chat/ZoomableImage'

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string }

export default function ChatPage({ user }: { user?: any }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSid, setCurrentSid] = useState<string>('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model] = useState(getStoredModel)
  const [quickInput, setQuickInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth > 768)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)
  const [images, setImages] = useState<string[]>([])
  const [expandedImage, setExpandedImage] = useState<string | null>(null)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const sidRef = useRef(currentSid)
  sidRef.current = currentSid

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth <= 768
      setIsMobile(mobile)
      if (mobile) setSidebarOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const refreshSessions = useCallback(async () => {
    const list = await listSessions()
    setSessions(list)
  }, [])

  useEffect(() => { refreshSessions() }, [refreshSessions])

  const handleNewSession = async () => {
    setCurrentSid('')
    setMessages([])
    setQuickInput('')
    setInput('')
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
        let reasoning: string | undefined
        let pageLink: string | undefined
        let content = m.content || ''
        if (typeof content === 'string' && content.startsWith('\x00META\x00')) {
          const end = content.indexOf('\x00', 6)
          if (end > 6) {
            try { const meta = JSON.parse(content.substring(6, end)); sender = meta.s; toolCalls = meta.t; reasoning = meta.r; pageLink = meta.p } catch {}
            content = content.substring(end + 1)
          }
        }
        return { role: m.role, content, images: m.images, sender, toolCalls, reasoning, pageLink }
      }))
    }
  }

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    await deleteSession(sid)
    if (currentSid === sid) { setCurrentSid(''); setMessages([]) }
    refreshSessions()
  }

  const SYSTEM_PROMPT = '你是小元AI的统筹助手，管理着数据分析、数据采集、自动化三个专业Agent团队。\n\n你可以委派的Agent：\n- delegate_to_analysis_agent：数据分析\n- delegate_to_collection_agent：数据采集\n- delegate_to_automation_agent：自动化\n\n工作原则：\n1. 判断意图，用一句话告诉用户将调用哪个Agent，然后立刻调用\n2. 子Agent返回结果后，如果结果已经清晰完整，只做简短确认如"以上是结果"，不要再复述\n3. 只有当结果需要解读、比较或给出建议时，才补充分析\n4. 用户能看到子Agent的输出，重复内容只会让对话冗余\n5. 对话结束或任务完成时，用表格总结本次完成了什么、关键结论是什么'

  const makeStreamHandlers = () => {
    let currentSender = 'orchestrator'
    const onEvent = (event: any) => {
      if (event.type === 'token') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data, sender: (last[i].sender || currentSender) as any }; return last })
      } else if (event.type === 'reasoning') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], reasoning: (last[i].reasoning || '') + event.data }; return last })
      } else if (event.type === 'tool_start') {
        const ns = senderFromTool(event.data.name)
        if (ns) { currentSender = ns; const sid =sidRef.current; const link =ns === 'analysis' && sid ? '/agent/dashboard/' + sid : ns === 'automation' ? '/agent/' + ns : undefined; setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: ns as any, pageLink: link, toolCalls: [{ name: event.data.name, status: 'running' as const }] }]) }
        else { setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[i] = { ...last[i], toolCalls: [...calls] } }; return last }) }
      } else if (event.type === 'tool_end') {
        const del_name =event.data.name || ''
        const isDel =!!senderFromTool(del_name)
        setMessages(function (prev) {
          const last =prev.slice()
          const i =last.length - 1
          if (i >= 0) {
            const calls =(last[i].toolCalls || []).map(function (c: any) { return c.name === del_name ? { name: c.name, status: 'done', result: event.data.output || '' } : c })
            last[i] = { role: last[i].role, content: last[i].content, sender: last[i].sender, toolCalls: calls, pageLink: last[i].pageLink, images: last[i].images }
          }
          return last
        })
        if (isDel) { currentSender = 'orchestrator'; setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: 'orchestrator', toolCalls: [] }]) }
      } else if (event.type === 'image') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].images = [...(last[i].images || []), event.data] }; return last })
      } else if (event.type === 'html') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].htmls = [...(last[i].htmls || []), event.data.url] }; return last })
      } else if (event.type === 'progress') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0 && last[i].role === 'assistant') last[i] = { ...last[i], progress: event.data }; return last })
      } else if (event.type === 'error') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: '请求失败，请重试' }; return last }); setLoading(false)
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
    const history = buildHistoryWithToolContext(prevMsgs)
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
    setInput(''); setQuickInput('')
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
        .chat-main { padding: 12px 4px !important; }
        .chat-welcome { padding: 3vh 8px 24px !important; }
        .chat-welcome h1 { font-size: 20px !important; }
        .chat-msg-bubble { max-width: 90% !important; }
        .chat-input-area { padding: 6px 6px 10px !important; }
        .chat-input-inner { max-width: 100% !important; }
        .chat-input-area textarea { font-size: 16px !important; }
      }
      @media (max-width: 480px) {
        .chat-msg-bubble { max-width: 94% !important; font-size: 13px !important; padding: 8px 12px !important; }
        .chat-welcome h1 { font-size: 18px !important; }
        .chat-input-area textarea { font-size: 16px !important; }
      }
    `}</style>
    <div style={{ height: '100%', display: 'flex', position: 'relative' }}>
      <Sidebar sessions={sessions} currentSid={currentSid} sidebarOpen={sidebarOpen} isMobile={isMobile}
        onNewSession={handleNewSession} onSelect={handleSelectSession} onDelete={handleDeleteSession} />

      {sidebarOpen && <div className="mobile-sidebar-backdrop" onClick={() => setSidebarOpen(false)} />}

      <div onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'absolute', left: isMobile ? 0 : (sidebarOpen ? 258 : 0), top: 64, zIndex: 10,
          padding: '12px 4px', borderRadius: '0 8px 8px 0',
          background: 'var(--bg-primary)', cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
          borderLeft: (!isMobile && sidebarOpen) ? 'none' : '1px solid var(--border)',
          boxShadow: (!isMobile && sidebarOpen) ? '1px 1px 4px var(--shadow-sm)' : '0 1px 3px var(--shadow-sm)',
          lineHeight: 1, transition: 'left 0.2s',
        }}
      >{sidebarOpen ? '◀' : '▶'}</div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {!currentSid ? (
          <WelcomePage
            images={images} setImages={setImages}
            quickInput={quickInput} setQuickInput={setQuickInput}
            sendWithNewSession={sendWithNewSession}
            sessions={sessions} onSelectSession={handleSelectSession}
          />
        ) : (
          <ChatView
            messages={messages} loading={loading} user={user}
            setExpandedImage={setExpandedImage}
            input={input} setInput={setInput} handleSend={handleSend}
            images={images} setImages={setImages}
            currentSid={currentSid}
            sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
            sessions={sessions}
          />
        )}
      </div>


      {expandedImage && (
        <ZoomableImage src={expandedImage} onClose={() => setExpandedImage(null)} />
      )}
    </div>
    </>
  )
}
