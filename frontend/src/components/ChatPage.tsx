import { useState, useRef, useEffect, useCallback } from 'react'
import { streamChat, createSession, listSessions, deleteSession, loadMessages, saveMessages, getStoredModel, API_BASE, getToken } from '../api'
import type { ChatMessage } from '../types'
import { senderFromTool, AGENT_CONFIG } from '../config/agents'
import { encodeMsg, buildHistoryWithToolContext } from './chat/helpers'
import Sidebar from './chat/Sidebar'
import WelcomePage from './chat/WelcomePage'
import ChatView from './chat/ChatView'
import ZoomableImage from './chat/ZoomableImage'

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string }

/* 兼容历史消息：路由迁移后旧路径 /agent/... 顶层已不存在（会落到兜底路由跳首页），渲染时统一补 /chat 前缀 */
function normalizePageLink(p: any): string | undefined {
  if (typeof p === 'string' && p.startsWith('/agent') && !p.startsWith('/chat')) return '/chat' + p
  return p
}

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
  // 聊天模式：local=本地统筹 Agent / cloud=云端直连 / claude=Claude Code 桥接
  const [chatMode, setChatMode] = useState<'local' | 'cloud' | 'claude'>('local')
  const [localOnline, setLocalOnline] = useState(false)
  const [claudeOnline, setClaudeOnline] = useState(false)
  const [statusKnown, setStatusKnown] = useState(false)
  // Claude Code 桥接待审批命令
  const [pendingApproval, setPendingApproval] = useState<{ decision_id: string; tool_name: string; command: string } | null>(null)
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

  // 轮询 Agent 在线状态（本地统筹 + Claude 桥接），供模式选择器置灰/点亮
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/agent-status`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (!res.ok) return
        const data = await res.json()
        if (Array.isArray(data)) {
          setLocalOnline(data.some((a: any) => !(a.capabilities || []).includes('claude_code')))
          setClaudeOnline(data.some((a: any) => (a.capabilities || []).includes('claude_code')))
          setStatusKnown(true)
        }
      } catch { /* 忽略轮询失败，保持上次状态 */ }
    }
    poll()
    const interval = setInterval(poll, 10000)
    return () => clearInterval(interval)
  }, [])

  // 当前模式对应的 Agent 掉线时自动回落到云端（首次轮询完成前不判定）
  useEffect(() => {
    if (!statusKnown) return
    if (chatMode === 'local' && !localOnline) setChatMode('cloud')
    if (chatMode === 'claude' && !claudeOnline) setChatMode('cloud')
  }, [chatMode, localOnline, claudeOnline, statusKnown])

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
            try { const meta = JSON.parse(content.substring(6, end)); sender = meta.s; toolCalls = meta.t; reasoning = meta.r; pageLink = normalizePageLink(meta.p) } catch {}
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

  const SYSTEM_PROMPT = '你是小元AI的统筹助手，管理着数据分析、数据采集、自动化三个专业Agent团队。\n\n你可以委派的Agent：\n- delegate_to_analysis_agent：数据分析\n- delegate_to_collection_agent：数据采集\n- delegate_to_automation_agent：自动化\n- delegate_to_claude_agent：本机 Claude Code（编写/修改代码、终端命令、Git 操作）\n\n工作原则：\n1. 判断意图，用一句话告诉用户将调用哪个Agent，然后立刻调用\n2. 子Agent返回结果后，如果结果已经清晰完整，只做简短确认如"以上是结果"，不要再复述\n3. 只有当结果需要解读、比较或给出建议时，才补充分析\n4. 用户能看到子Agent的输出，重复内容只会让对话冗余\n5. 对话结束或任务完成时，用表格总结本次完成了什么、关键结论是什么'

  const makeStreamHandlers = () => {
    let currentSender = 'orchestrator'
    const onEvent = (event: any) => {
      if (event.type === 'token') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data, sender: (last[i].sender || currentSender) as any }; return last })
      } else if (event.type === 'reasoning') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], reasoning: (last[i].reasoning || '') + event.data }; return last })
      } else if (event.type === 'tool_start') {
        const ns = senderFromTool(event.data.name)
        if (ns) { currentSender = ns; const sid =sidRef.current; const link =ns === 'analysis' && sid ? '/chat/agent/dashboard/' + sid : ns === 'automation' ? '/chat/agent/' + ns : undefined; setMessages((prev) => [...prev, { role: 'assistant' as const, content: '', sender: ns as any, pageLink: link, toolCalls: [{ name: event.data.name, status: 'running' as const }] }]) }
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
      } else if (event.type === 'agent') {
        // Claude 桥接声明身份：后续 token 归属该 Agent 气泡（复用尾部空占位气泡，不新增）
        const ns = event.data.sender
        if (ns && AGENT_CONFIG[ns]) {
          currentSender = ns
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'assistant' && !last.content && !(last.toolCalls?.length)) {
              return [...prev.slice(0, -1), { ...last, sender: ns as any }]
            }
            return [...prev, { role: 'assistant' as const, content: '', sender: ns as any, toolCalls: [] }]
          })
        }
      } else if (event.type === 'approval') {
        setPendingApproval({ decision_id: event.data.decision_id, tool_name: event.data.tool_name, command: event.data.command })
      } else if (event.type === 'error') {
        // 展示真实错误信息（截断），便于排查
        const errMsg = typeof event.data === 'string' && event.data ? event.data.slice(0, 300) : '请求失败，请重试'
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: `请求失败: ${errMsg}` }; return last }); setLoading(false)
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
    // 普通消息自动撤销未决审批（桥接侧会 deny pending 后正常处理）
    setPendingApproval(null)
    const history = buildHistoryWithToolContext(prevMsgs)
    const placeholderSender = chatMode === 'claude' ? 'claude' : 'orchestrator'
    setMessages((prev) => [...prev, { role: 'assistant', content: '', sender: placeholderSender as any, toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt: input, images: sentImages, history, system_prompt: SYSTEM_PROMPT,
        session_id: chatMode === 'claude' ? sid : undefined, claude: chatMode === 'claude', force_cloud: chatMode === 'cloud' },
      onEvent, onError,
      () => {
        setLoading(false)
        const msgs = messagesRef.current.map(encodeMsg)
        saveMessages(sid, msgs, input.length > 50 ? input.slice(0, 50) + '...' : input)
        refreshSessions()
      },
    )
  }

  // 审批决议：走 Claude 桥接专用流，body 带 decision
  const handleDecision = (approve: boolean) => {
    const pa = pendingApproval
    setPendingApproval(null)
    if (!pa || !currentSid) return
    streamChat(
      { model, temperature: 0.7, prompt: '', history: [], system_prompt: SYSTEM_PROMPT,
        session_id: currentSid, decision: { decision_id: pa.decision_id, approve }, claude: true },
      () => {}, () => {},
      () => { setLoading(false) },
    )
  }

  const sendWithNewSession = async (text: string) => {
    setLoading(true)
    const sid = await createSession()
    setCurrentSid(sid); refreshSessions()
    setInput(''); setQuickInput('')
    const sentImages = [...images]; setImages([])
    setMessages([{ role: 'user', content: text, images: sentImages.length > 0 ? sentImages : undefined }])
    const placeholderSender = chatMode === 'claude' ? 'claude' : 'orchestrator'
    setMessages((prev) => [...prev, { role: 'assistant', content: '', sender: placeholderSender as any, toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt: text, images: sentImages.length > 0 ? sentImages : undefined, history: [], system_prompt: SYSTEM_PROMPT,
        session_id: chatMode === 'claude' ? sid : undefined, claude: chatMode === 'claude', force_cloud: chatMode === 'cloud' },
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
            chatMode={chatMode} setChatMode={setChatMode}
            localOnline={localOnline} claudeOnline={claudeOnline}
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
            chatMode={chatMode} setChatMode={setChatMode}
            localOnline={localOnline} claudeOnline={claudeOnline}
            pendingApproval={pendingApproval} handleDecision={handleDecision}
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
