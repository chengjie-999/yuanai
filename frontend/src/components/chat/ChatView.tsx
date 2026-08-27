import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ChatMode } from './ChatModeSelector'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'
import ApprovalCard from './ApprovalCard'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, currentSid, sidebarOpen, setSidebarOpen, sessions, chatMode, setChatMode, localOnline, claudeOnline, pendingApproval, handleDecision, likes, editingIndex, setEditingIndex, onEditMessage, onLike }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string) => void; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void
  sessions: SessionInfo[]
  chatMode: ChatMode; setChatMode: (v: ChatMode) => void
  localOnline: boolean; claudeOnline: boolean
  pendingApproval: { decision_id: string; tool_name: string; command: string } | null
  handleDecision: (approve: boolean) => void
  likes: Record<number, boolean>
  editingIndex: number | null
  setEditingIndex: (v: number | null) => void
  onEditMessage: (index: number, content: string) => void
  onLike: (index: number) => void
}) {
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingApproval])

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
              liked={!!likes[i]} editing={editingIndex === i}
              setExpandedImage={setExpandedImage}
              onEditStart={setEditingIndex}
              onEditConfirm={onEditMessage}
              onEditCancel={() => setEditingIndex(null)}
              onLike={onLike} />
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
        sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
        sessions={sessions} messages={messages}
        chatMode={chatMode} setChatMode={setChatMode}
        localOnline={localOnline} claudeOnline={claudeOnline} />
    </>
  )
}
