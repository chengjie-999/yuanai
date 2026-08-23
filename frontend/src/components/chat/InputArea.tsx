import { useRef, useState } from 'react'
import { downloadChat } from './helpers'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ChatMode } from './ChatModeSelector'
import ChatModeSelector from './ChatModeSelector'
import { compressImage } from './imageUtils'

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, currentSid, sidebarOpen, setSidebarOpen, sessions, messages, chatMode, setChatMode, localOnline, claudeOnline }: {
  input: string; setInput: (v: string) => void; loading: boolean; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void
  sessions: SessionInfo[]; messages: ChatMessage[]
  chatMode: ChatMode; setChatMode: (v: ChatMode) => void
  localOnline: boolean; claudeOnline: boolean
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  return (
    <div className="chat-input-area" style={{ padding: '12px 24px 20px', borderTop: '1px solid var(--border)' }}>
      <div className="chat-input-inner" style={{ maxWidth: 720, margin: '0 auto', width: '100%', boxShadow: '0 4px 24px var(--shadow-sm)' }}>
        <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-input)', transition: 'box-shadow 0.2s' }}
          onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px var(--shadow-sm)'}
          onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
        >
          {uploading && (
            <div style={{ fontSize: 12, color: 'var(--accent)', padding: '8px 12px 0', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              正在压缩图片…
            </div>
          )}
          {images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, padding: '8px 12px 0', overflowX: 'auto' }}>
              {images.map((img, i) => (
                <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                  <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid var(--border)' }} />
                  <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                    style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: 'var(--danger)', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
            <textarea value={input} onChange={(e) => { setInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; t.style.overflowY = t.scrollHeight > 200 ? 'auto' : 'hidden' }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="输入消息..." disabled={loading}
              rows={1}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflow: 'hidden', color: 'var(--text-primary)' }}
            />
            <input ref={fileRef} type="file" accept="image/*" multiple hidden
              onChange={(e) => {
                const files = e.target.files
                if (files) {
                  setUploading(true)
                  Promise.all(Array.from(files).map(async (f) => {
                    try {
                      return await compressImage(f)
                    } catch {
                      return await new Promise<string>((resolve) => {
                        const reader = new FileReader()
                        reader.onload = () => resolve(reader.result as string)
                        reader.readAsDataURL(f)
                      })
                    }
                  })).then((results) => {
                    setImages((p) => [...p, ...results])
                    setUploading(false)
                  }).catch(() => setUploading(false))
                  e.target.value = ''
                }
              }}
            />
            <button onClick={() => fileRef.current?.click()} title="上传图片"
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--text-secondary)', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
            >📎</button>
            <button onClick={handleSend} disabled={loading || !input.trim() || !currentSid}
              className="btn btn-primary"
              style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, borderRadius: 10, opacity: loading || !input.trim() || !currentSid ? 0.5 : 1 }}
            >{loading ? '...' : '发送'}</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px 10px' }}>
            <button onClick={() => {
              const s = sessions.find(s => s.session_id === currentSid)
              downloadChat(messages, `${s?.title || 'chat'}.txt`)
            }} title="下载聊天记录" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: 'var(--text-muted)', padding: '2px 4px', lineHeight: 1, opacity: 0.6, transition: 'opacity 0.15s' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0.6'}
            >📥</button>
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12, padding: 0 }}>▶ 侧栏</button>
            )}
            <ChatModeSelector chatMode={chatMode} setChatMode={setChatMode}
              localOnline={localOnline} claudeOnline={claudeOnline} />
          </div>
        </div>
      </div>
    </div>
  )
}
