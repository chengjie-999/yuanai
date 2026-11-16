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
  const voiceSessionRef = useRef<string | null>(null)
  const pendingVoiceTranscriptsRef = useRef<{ role: 'user' | 'assistant'; content: string; msgId: string }[]>([])

  const ensureVoiceSession = async (): Promise<string> => {
    const cur = ctx.sidRef.current
    if (cur) { voiceSessionRef.current = cur; return cur }
    const sid = await createSession()
    voiceSessionRef.current = sid
    ctx.setCurrentSid(sid)
    ctx.refreshSessions()
    return sid
  }

  // 打开语音聊天卡（2026-11-14 半双工：按住说话 → ASR → 发送 → 自动朗读）
  const startVoiceCall = () => {
    pendingVoiceTranscriptsRef.current = []
    setVoiceCallOpen(true)
  }

  // 语音转录：只落库拿 msg_id，不追加 UI（单一写路径——用户气泡由发送链路追加，
  // 带同 id 落库 upsert 幂等）。2026-11-16 修复根因：此前 await voiceMessage 后
  // 把转录气泡追加到最后，落在 assistant 占位气泡之后——SSE 流式按「最后一条」
  // 更新，AI 回答全写进用户消息，且消息显示两遍。
  // 返回：null=已切走（只落库不发送）；'queued'=AI 生成中（UI 排队，流结束 flush）；
  // 其余=msg_id（网络失败返回 ''，仍要发送）。信封协议：assistant 转录补
  // sender=orchestrator（模型回复身份），user 无 sender。
  const handleVoiceTranscript = async (role: 'user' | 'assistant', content: string): Promise<string | null> => {
    const sid = voiceSessionRef.current
    if (!sid) return ''
    // 一律先落库（loading 与否都先持久化——关页也不丢）；flush 不再二次落库
    const msgId = await voiceMessage(sid, role, content)
    if (sid !== ctx.sidRef.current) return null  // 用户切走了：只落库，展示等切回后 loadMessages 出现
    if (ctx.loadingRef.current) {
      // AI 正在回答（await 后重查，防期间翻转）：队列条目带 msg_id，流结束按 id 追加
      pendingVoiceTranscriptsRef.current.push({ role, content, msgId })
      return 'queued'
    }
    return msgId
  }

  // 文字流结束：把暂存的语音转录并入保存快照（带 msg_id——落库已在转录时完成，
  // save upsert 按 id 跳过已存在行，轮询去重生效；不再二次 voiceMessage 落库）
  const flushVoiceTranscripts = (msgs: ChatMessage[]): ChatMessage[] => {
    const queued = pendingVoiceTranscriptsRef.current.splice(0)
    if (!queued.length) return msgs
    const sid = voiceSessionRef.current
    if (sid === ctx.sidRef.current) {
      const withFlush = [...msgs, ...queued.map((q) => ({
        role: q.role, content: q.content,
        ...(q.msgId ? { msg_id: q.msgId } : {}),
        ...(q.role === 'assistant' ? { sender: 'orchestrator' as const } : {}),
      }))]
      ctx.setMessages(withFlush)
      return withFlush
    }
    // 已切到别的会话：落库已完成，不污染当前视图
    return msgs
  }

  return {
    voiceCallOpen, setVoiceCallOpen,
    ensureVoiceSession, startVoiceCall,
    handleVoiceTranscript, flushVoiceTranscripts,
  }
}
