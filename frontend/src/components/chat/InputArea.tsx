import { useRef } from 'react'
import { ModelSelector } from '../ModelSelector'
import { downloadChat } from './helpers'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'

import type { PanelType } from './SidePanel'

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, model, setModel, currentSid, sidebarOpen, setSidebarOpen, sessions, messages, panel, setPanel }: {
  input: string; setInput: (v: string) => void; loading: boolean; handleSend: () => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  model: string; setModel: (v: string) => void; currentSid: string
  sidebarOpen: boolean; setSidebarOpen: (v: boolean) => void
  sessions: SessionInfo[]; messages: ChatMessage[]
  panel: PanelType; setPanel: (v: PanelType) => void
}) {
  const PANELS: PanelType[] = ['automation', 'analysis', 'knowledge']
  const fileRef = useRef<HTMLInputElement>(null)

  return (
    <div className="chat-input-area" style={{ padding: '12px 24px 20px', borderTop: '1px solid #eee' }}>
      <div className="chat-input-inner" style={{ maxWidth: 720, margin: '0 auto', width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
        <div style={{ border: '1px solid #e0e0e0', borderRadius: 14, background: '#fff', transition: 'box-shadow 0.2s' }}
          onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px rgba(0,0,0,0.06)'}
          onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
        >
          {images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, padding: '8px 12px 0', overflowX: 'auto' }}>
              {images.map((img, i) => (
                <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                  <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid #eee' }} />
                  <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                    style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: '#e53935', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
            <textarea value={input} onChange={(e) => { setInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px' }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="输入消息... (Enter 发送，Shift+Enter 换行)" disabled={loading}
              rows={1}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflowY: 'auto' }}
            />
            <input ref={fileRef} type="file" accept="image/*" multiple hidden
              onChange={(e) => {
                const files = e.target.files
                if (files) {
                  Array.from(files).forEach((f) => {
                    const reader = new FileReader()
                    reader.onload = () => setImages((p) => [...p, reader.result as string])
                    reader.readAsDataURL(f)
                  })
                  e.target.value = ''
                }
              }}
            />
            <button onClick={() => fileRef.current?.click()} title="上传图片"
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#999', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
            >📎</button>
            <button onClick={handleSend} disabled={loading || !input.trim() || !currentSid}
              className="btn btn-primary"
              style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, borderRadius: 10, opacity: loading || !input.trim() || !currentSid ? 0.5 : 1 }}
            >{loading ? '...' : '发送'}</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px 10px' }}>
            <ModelSelector model={model} onChange={(v) => { setModel(v) }} />
            <button onClick={() => {
              const s = sessions.find(s => s.session_id === currentSid)
              downloadChat(messages, `${s?.title || 'chat'}.txt`)
            }} title="下载聊天记录" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#bbb', padding: '2px 4px', lineHeight: 1, opacity: 0.6, transition: 'opacity 0.15s' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '0.6'}
            >📥</button>
            {!sidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} style={{ background: 'none', border: 'none', color: '#999', cursor: 'pointer', fontSize: 12, padding: 0 }}>▶ 侧栏</button>
            )}
            <button
              onClick={() => {
                const idx = PANELS.indexOf(panel as PanelType)
                setPanel(panel ? PANELS[(idx + 1) % PANELS.length] : PANELS[0])
              }}
              title="切换面板（测试）"
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: '#bbb', padding: '2px 4px', opacity: 0.5 }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.5')}
            >▸ 面板</button>
          </div>
        </div>
      </div>
    </div>
  )
}
