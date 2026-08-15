import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'
import ApprovalCard from './ApprovalCard'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, currentSid, sidebarOpen, setSidebarOpen, sessions, claudeMode, setClaudeMode, pendingApproval, handleDecision }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string) => void; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void
  sessions: SessionInfo[]
  claudeMode: boolean; setClaudeMode: (v: boolean) => void
  pendingApproval: { decision_id: string; tool_name: string; command: string } | null
  handleDecision: (approve: boolean) => void
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
            <MessageBubble key={i} msg={msg} isLast={i === messages.length - 1}
              loading={loading} user={user}
              setExpandedImage={setExpandedImage} />
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
        claudeMode={claudeMode} setClaudeMode={setClaudeMode} />
    </>
  )
}
