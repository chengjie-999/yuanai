import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ChatMode } from './ChatModeSelector'
import type { ReasoningEffort } from './ReasoningSelector'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'
import ApprovalCard from './ApprovalCard'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, currentSid, sessions, chatMode, setChatMode, localOnline, claudeOnline, effort, setEffort, autoRead, setAutoRead, autoReadTick, pendingApproval, handleDecision, likes, editingIndex, setEditingIndex, onEditMessage, onFeedback, onStartVoiceCall }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string) => void; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]
  chatMode: ChatMode; setChatMode: (v: ChatMode) => void
  localOnline: boolean; claudeOnline: boolean
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  autoRead: boolean; setAutoRead: (v: boolean) => void; autoReadTick: number
  pendingApproval: { decision_id: string; tool_name: string; command: string } | null
  handleDecision: (approve: boolean) => void
  likes: Record<number, { liked: boolean; disliked: boolean }>
  editingIndex: number | null
  setEditingIndex: (v: number | null) => void
  onEditMessage: (index: number, content: string) => void
  onFeedback: (index: number, kind: 'like' | 'dislike') => void
  onStartVoiceCall: () => void
}) {
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // 流式输出时用 auto（无动画）且只在用户贴近底部时跟随——
    // 防止逐 token 平滑滚动造成「一上一下闪」的抖动
    const el = chatEndRef.current
    if (!el) return
    const container = el.closest('.chat-main')
    if (!container) { el.scrollIntoView({ behavior: 'auto' }); return }
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120
    if (nearBottom) el.scrollIntoView({ behavior: loading ? 'auto' : 'smooth' })
  }, [messages, pendingApproval, loading])

  return (
    <>
      <div className="chat-main" style={{
        flex: 1, overflowY: 'auto', padding: '32px 16px 16px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        background: 'var(--bg-primary)',
      }}>
        <div style={{ maxWidth: 720, width: '100%' }}>
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} index={i} isLast={i === messages.length - 1}
              loading={loading} user={user}
              liked={!!likes[i]?.liked} disliked={!!likes[i]?.disliked} editing={editingIndex === i}
              autoRead={autoRead} autoReadTick={autoReadTick}
              setExpandedImage={setExpandedImage}
              onEditStart={setEditingIndex}
              onEditConfirm={onEditMessage}
              onEditCancel={() => setEditingIndex(null)}
              onFeedback={onFeedback} />
          ))}
          <div ref={chatEndRef} />
          {pendingApproval && (
            <div style={{ display: 'flex', justifyContent: 'flex-start', maxWidth: 720, width: '100%' }}>
              <ApprovalCard
                decisionId={pendingApproval.decision_id}
                toolName={pendingApproval.tool_name}
                command={pendingApproval.command}
                onDecision={handleDecision}
              />
            </div>
          )}
        </div>
      </div>

      <InputArea input={input} setInput={setInput} loading={loading}
        handleSend={handleSend} images={images} setImages={setImages}
        currentSid={currentSid}
        sessions={sessions} messages={messages}
        chatMode={chatMode} setChatMode={setChatMode}
        localOnline={localOnline} claudeOnline={claudeOnline}
        effort={effort} setEffort={setEffort}
        autoRead={autoRead} setAutoRead={setAutoRead}
        onStartVoiceCall={onStartVoiceCall} />
    </>
  )
}
