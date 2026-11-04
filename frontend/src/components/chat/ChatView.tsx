import { useRef, useEffect, useState } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ReasoningEffort } from './ReasoningSelector'
import { SUGGESTIONS, ENT_SUGGESTIONS } from '../../config/agents'
import { ArrowDownIcon } from '../icons'
import Mascot from '../Mascot'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'
import ApprovalCard from './ApprovalCard'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, currentSid, sessions, localOnline, claudeOnline, model, setModel, effort, setEffort, autoRead, autoReadTick, pendingApproval, handleDecision, likes, editingIndex, setEditingIndex, onEditMessage, onFeedback, onReport, onRegenerate, onContinue, onStartVoiceCall, entMode, toggleEntMode, targetAgent, setTargetAgent, onOpenDirectChat, onStop, notice, onSuggest, sendTick, onOpenPanel }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string | ((p: string) => string)) => void; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]
  localOnline: boolean; claudeOnline: boolean
  model: string; setModel: (v: string) => void
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  autoRead: boolean; autoReadTick: number
  pendingApproval: { decision_id: string; tool_name: string; command: string; claude: boolean } | null
  handleDecision: (approve: boolean) => void
  likes: Record<number, { liked: boolean; disliked: boolean }>
  editingIndex: number | null
  setEditingIndex: (v: number | null) => void
  onEditMessage: (index: number, content: string) => void
  onFeedback: (index: number, kind: 'like' | 'dislike') => void
  onReport: (index: number) => void
  onRegenerate: (index: number) => void
  onContinue: () => void
  onStartVoiceCall: () => void
  entMode: boolean
  toggleEntMode: () => void
  targetAgent: string
  setTargetAgent: (v: string) => void
  onOpenDirectChat: (target: string) => void
  onStop: () => void
  notice: string
  onSuggest: (text: string) => void
  sendTick: number
  onOpenPanel: (link: string) => void
}) {
  const chatEndRef = useRef<HTMLDivElement>(null)
  const lastSidRef = useRef(currentSid)
  const lastSendTickRef = useRef(sendTick)
  // 是否贴底（滚动监听实时维护）：贴底才跟随最新消息；上滑阅读时暂停跟随
  const nearBottomRef = useRef(true)
  // B3 修复（2026-10-26）：防顶屏冻结只钉一次——冻结期间程序化滚动不再触发
  // 重钉，且冻结态不随「短暂贴底」抖动复位；用户主动下滑 >40px 才恢复跟随
  const frozenRef = useRef(false)
  const pinnedTopRef = useRef(0)
  const [showJump, setShowJump] = useState(false)
  // 会话是否「没内容」（2026-10-31 用户拍板：新对话与其他空情况统一显示吉祥物）
  const isEmpty = !messages.some((m) =>
    (m.content && m.content.trim()) || m.error || m.images?.length || m.toolCalls?.length)

  const jumpToBottom = () => {
    const container = chatEndRef.current?.closest('.chat-main') as HTMLElement | null
    if (!container) return
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    nearBottomRef.current = true
    frozenRef.current = false
    setShowJump(false)
  }

  useEffect(() => {
    const container = chatEndRef.current?.closest('.chat-main') as HTMLElement | null
    if (!container) return
    const onScroll = () => {
      const near = container.scrollHeight - container.scrollTop - container.clientHeight < 120
      if (frozenRef.current) {
        // 冻结期间：程序化钉顶产生的短暂贴底不解除冻结；
        // 只有用户继续向下滚动超过 40px（追上内容）才恢复跟随
        if (near && container.scrollTop > pinnedTopRef.current + 40) {
          frozenRef.current = false
          nearBottomRef.current = true
          setShowJump(false)
        } else {
          setShowJump(true)
          return
        }
      }
      nearBottomRef.current = near
      setShowJump(!near)
    }
    container.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => container.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    // 进入/切换会话（含登录落主对话）、发送/修改重发：无条件直达最新消息并
    // 恢复跟随——用户习惯，不看当前位置判定（刚进入时 scrollTop=0 会被误判）
    const sessionChanged = lastSidRef.current !== currentSid
    lastSidRef.current = currentSid
    const justSent = lastSendTickRef.current !== sendTick
    lastSendTickRef.current = sendTick
    const el = chatEndRef.current
    if (!el) return
    const container = el.closest('.chat-main') as HTMLElement | null
    if (!container) { el.scrollIntoView({ behavior: 'auto' }); return }
    if (sessionChanged || justSent) {
      container.scrollTop = container.scrollHeight
      nearBottomRef.current = true
      frozenRef.current = false
      setShowJump(false)
      return
    }
    // 流式输出：贴底才跟随，直接设 scrollTop（无平滑动画）防逐 token 抖动；
    // 上滑阅读历史时暂停跟随，点「回到底部」按钮恢复。
    // 长回答防顶屏（2026-10-25）：回答超过一屏时生成速度超过阅读速度——
    // 最后一条消息顶部即将滚出视口时，把消息顶部钉在视口顶部并冻结跟随；
    // B3（2026-10-26）：钉住一次后冻结（frozenRef），不再逐 token 重复校正，
    // 抖动消除；用户下滑 >40px 或点「回到底部」恢复跟随
    if (frozenRef.current) return
    if (nearBottomRef.current) {
      const lastEl = chatEndRef.current?.previousElementSibling as HTMLElement | null
      const crect = container.getBoundingClientRect()
      const lrect = lastEl ? lastEl.getBoundingClientRect() : null
      if (lrect && lrect.top < crect.top + 8) {
        container.scrollTop += (lrect.top - crect.top - 8)
        pinnedTopRef.current = container.scrollTop
        frozenRef.current = true
        nearBottomRef.current = false
        setShowJump(true)
        return
      }
      container.scrollTop = container.scrollHeight
    }
  }, [messages, pendingApproval, loading, currentSid, sendTick])

  return (
    <>
      <div className="chat-main" style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden',  // 溢出修复：整页不再横向滚动
        padding: '32px 16px 16px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        background: 'var(--bg-primary)',
      }}>
        <div style={{ maxWidth: 720, width: '100%' }}>
          {messages.map((msg, i) => (
            <MessageBubble key={`${currentSid}-${i}`} msg={msg} index={i} isLast={i === messages.length - 1}
              loading={loading} user={user}
              liked={!!likes[i]?.liked} disliked={!!likes[i]?.disliked} editing={editingIndex === i}
              autoRead={autoRead} autoReadTick={autoReadTick}
              setExpandedImage={setExpandedImage}
              onEditStart={setEditingIndex}
              onEditConfirm={onEditMessage}
              onEditCancel={() => setEditingIndex(null)}
              onFeedback={onFeedback}
              onReport={onReport}
              onRegenerate={onRegenerate}
              onFollowup={onSuggest}
              onContinue={onContinue}
              onOpenPanel={onOpenPanel} />
          ))}
          {/* 空对话推荐问题（豆包式：欢迎页已退场，登录直接落主对话，此处承接快捷入口）；
              E5：娱乐模式换娱乐话题卡。
              2026-10-31 用户拍板：新对话及其他所有没内容的情况（降级后空对话/
              出错后/停止后空泡）都显示吉祥物 + 推荐问题 */}
          {isEmpty && !loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', marginTop: 6 }}>
              {/* 空对话吉祥物：只显示主页 logo 形象，不加问候语（2026-10-31 用户拍板） */}
              <Mascot size={72} />
              <div style={{ height: 12 }} />
            </div>
          )}
          {isEmpty && !loading && (
            <div className="chat-suggest-row" style={{
              display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4,
            }}>
              {(entMode ? ENT_SUGGESTIONS : SUGGESTIONS).slice(0, 5).map((s) => (
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

        {/* 回到底部：上滑阅读时浮出（sticky 钉在可视区底部），点击滚回最新并恢复跟随 */}
        <button
          className="yuan-jump-bottom yuan-tip"
          onClick={jumpToBottom}
          aria-label="回到底部"
          data-tip="回到底部"
          style={{
            position: 'sticky', bottom: 16, alignSelf: 'center', marginTop: -44,
            width: 36, height: 36, borderRadius: '50%', zIndex: 5,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--bg-input)', border: '1px solid var(--border)',
            boxShadow: '0 2px 12px rgba(0, 0, 0, 0.14)', cursor: 'pointer',
            color: 'var(--text-secondary)',
            opacity: showJump ? 1 : 0,
            transform: showJump ? 'translateY(0)' : 'translateY(8px)',
            pointerEvents: showJump ? 'auto' : 'none',
            transition: 'opacity 0.2s, transform 0.2s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'var(--accent)' }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'var(--border)' }}
        >
          <ArrowDownIcon size={18} />
        </button>
      </div>

      <InputArea input={input} setInput={setInput} loading={loading}
        handleSend={handleSend} images={images} setImages={setImages}
        currentSid={currentSid}
        sessions={sessions} messages={messages}
        localOnline={localOnline} claudeOnline={claudeOnline}
        model={model} setModel={setModel}
        effort={effort} setEffort={setEffort}
        onStartVoiceCall={onStartVoiceCall}
        entMode={entMode} toggleEntMode={toggleEntMode}
        targetAgent={targetAgent} setTargetAgent={setTargetAgent}
        onOpenDirectChat={onOpenDirectChat}
        onStop={onStop} notice={notice} />
    </>
  )
}
