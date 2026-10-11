import { useRef, useState, type MutableRefObject } from 'react'
import type { ChatMessage } from '../../types'
import { createSession, voiceMessage } from '../../api'

/**
 * 语音通话状态机（从 ChatPage 抽出）：
 * - 会话锚定：通话开始时一次 pin（欢迎页自动新建并切进聊天页），转录统一落该会话
 * - 转录队列：文字流式期间暂存，流结束 flush 并入 /chat/save 快照（防被全量替换抹掉）
 * - 视图隔离：转录 UI 只追加到通话所属会话，切走时仅落库
 * 所有跨渲染的值走 ref（ctx），避免 mount-effect 冻结闭包。
 */
export function useVoiceCall(ctx: {
  sidRef: MutableRefObject<string>
  messagesRef: MutableRefObject<ChatMessage[]>
  loadingRef: MutableRefObject<boolean>
  setMessages: (v: ChatMessage[] | ((p: ChatMessage[]) => ChatMessage[])) => void
  setCurrentSid: (v: string) => void
  refreshSessions: () => Promise<void>
}) {
  const [voiceCallOpen, setVoiceCallOpen] = useState(false)
  // 最近一条 AI 文字回复（供语音通话「朗读文字回复」朗读）
  const [lastAssistantText, setLastAssistantText] = useState('')
  const voiceSessionRef = useRef<string | null>(null)
  const pendingVoiceTranscriptsRef = useRef<{ role: 'user' | 'assistant'; content: string }[]>([])

  const ensureVoiceSession = async (): Promise<string> => {
    const cur = ctx.sidRef.current
    if (cur) { voiceSessionRef.current = cur; return cur }
    const sid = await createSession()
    voiceSessionRef.current = sid
    ctx.setCurrentSid(sid)
    ctx.refreshSessions()
    return sid
  }

  // 开始语音通话：清掉历史文字回复，避免通话时误朗读旧消息造成重音
  const startVoiceCall = () => {
    setLastAssistantText('')
    pendingVoiceTranscriptsRef.current = []
    setVoiceCallOpen(true)
  }

  // 语音转录：持久化锚定通话会话；UI 仅追加到通话所属会话视图；loading 期间进队列
  // 信封协议：assistant 转录补 sender=orchestrator（模型回复身份），user 无 sender
  const handleVoiceTranscript = (role: 'user' | 'assistant', content: string) => {
    const sid = voiceSessionRef.current
    if (ctx.loadingRef.current) {
      pendingVoiceTranscriptsRef.current.push({ role, content })
      return
    }
    if (sid) voiceMessage(sid, role, content)
    if (sid && sid !== ctx.sidRef.current) return  // 用户切走了：只落库，展示等切回后 loadMessages 出现
    ctx.setMessages((prev) => [...prev, { role, content, ...(role === 'assistant' ? { sender: 'orchestrator' as const } : {}) }])
  }

  // 文字流结束：把暂存的语音转录并入保存快照（进入 /chat/save 全量替换，避免被抹掉）
  const flushVoiceTranscripts = (msgs: ChatMessage[]): ChatMessage[] => {
    const queued = pendingVoiceTranscriptsRef.current.splice(0)
    if (!queued.length) return msgs
    const sid = voiceSessionRef.current
    if (sid === ctx.sidRef.current) {
      const withFlush = [...msgs, ...queued.map((q) => ({ role: q.role, content: q.content, ...(q.role === 'assistant' ? { sender: 'orchestrator' as const } : {}) }))]
      ctx.setMessages(withFlush)
      return withFlush
    }
    // 已切到别的会话：不污染当前视图，逐条补持久化到通话会话
    if (sid) queued.forEach((q) => voiceMessage(sid, q.role, q.content))
    return msgs
  }

  // 记录最新 AI 回复全文（语音通话朗读用；排除转录气泡：带 sender 的才是模型回复）
  const noteLastAssistant = (msgs: ChatMessage[]) => {
    const lastA = [...msgs].reverse().find((m) => m.role === 'assistant' && m.content && m.sender)
    if (lastA) setLastAssistantText(lastA.content)
  }

  return {
    voiceCallOpen, setVoiceCallOpen, lastAssistantText,
    ensureVoiceSession, startVoiceCall,
    handleVoiceTranscript, flushVoiceTranscripts, noteLastAssistant,
  }
}
