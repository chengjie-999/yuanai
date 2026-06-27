import { useRef, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import MessageBubble from './MessageBubble'
import InputArea from './InputArea'

export default function ChatView({ messages, loading, user, setExpandedImage, input, setInput, handleSend, images, setImages, model, setModel, currentSid, sidebarOpen, setSidebarOpen, sessions }: {
  messages: ChatMessage[]; loading: boolean; user?: any
  setExpandedImage: (v: string | null) => void
  input: string; setInput: (v: string) => void; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  model: string; setModel: (v: string) => void; currentSid: string
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void
  sessions: SessionInfo[]
}) {
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <>
      <div className="chat-main" style={{
        flex: 1, overflowY: 'auto', padding: '32px 16px 16px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
      }}>
        <div style={{ maxWidth: 720, width: '100%' }}>
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} isLast={i === messages.length - 1}
              loading={loading} user={user}
              setExpandedImage={setExpandedImage} />
          ))}
          <div ref={chatEndRef} />
        </div>
      </div>

      <InputArea input={input} setInput={setInput} loading={loading}
        handleSend={handleSend} images={images} setImages={setImages}
        model={model} setModel={setModel} currentSid={currentSid}
        sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}
        sessions={sessions} messages={messages} />
    </>
  )
}
