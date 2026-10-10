import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ReasoningEffort } from './ReasoningSelector'
import { SUGGESTIONS } from '../../config/agents'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'
import ApprovalCard from './ApprovalCard'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, currentSid, sessions, localOnline, claudeOnline, effort, setEffort, autoRead, autoReadTick, pendingApproval, handleDecision, likes, editingIndex, setEditingIndex, onEditMessage, onFeedback, onStartVoiceCall, targetAgent, setTargetAgent, onSuggest }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string | ((p: string) => string)) => void; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]
  localOnline: boolean; claudeOnline: boolean
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  autoRead: boolean; autoReadTick: number
  pendingApproval: { decision_id: string; tool_name: string; command: string } | null
  handleDecision: (approve: boolean) => void
  likes: Record<number, { liked: boolean; disliked: boolean }>
  editingIndex: number | null
  setEditingIndex: (v: number | null) => void
  onEditMessage: (index: number, content: string) => void
  onFeedback: (index: number, kind: 'like' | 'dislike') => void
  onStartVoiceCall: () => void
  targetAgent: string
  setTargetAgent: (v: string) => void
  onSuggest: (text: string) => void
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
          {/* 空对话推荐问题（豆包式：欢迎页已退场，登录直接落主对话，此处承接快捷入口） */}
          {messages.length <= 1 && !loading && (
            <div className="chat-suggest-row" style={{
              display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4,
            }}>
              {SUGGESTIONS.slice(0, 5).map((s) => (
                <button key={s.text} onClick={() => onSuggest(s.text)}
                  style={{
                    padding: '5px 10px', borderRadius: 999, border: '1px solid var(--border)',
                    background: 'var(--bg-input)', cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)',
                    transition: 'all 0.15s', whiteSpace: 'nowrap',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
                >{s.text}</button>
              ))}
            </div>
          )}
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
        localOnline={localOnline} claudeOnline={claudeOnline}
        effort={effort} setEffort={setEffort}
        onStartVoiceCall={onStartVoiceCall}
        targetAgent={targetAgent} setTargetAgent={setTargetAgent} />
    </>
  )
}
