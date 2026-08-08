import { useRef } from 'react'
import { ModelSelector } from '../ModelSelector'
import { SUGGESTIONS } from '../../config/agents'
import { uploadDataset } from '../../api'
import Mascot from '../Mascot'
import type { SessionInfo } from './helpers'

export default function WelcomePage({ images, setImages, quickInput, setQuickInput, sendWithNewSession, model, setModel, sessions, onSelectSession }: {
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  quickInput: string; setQuickInput: (v: string | ((p: string) => string)) => void
  sendWithNewSession: (text: string) => void
  model: string; setModel: (v: string) => void
  sessions: SessionInfo[]; onSelectSession: (sid: string) => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)

  return (
    <div className="chat-welcome" style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '6vh 16px 40px', minHeight: 0, overflowY: 'auto',
      background: 'var(--bg-primary)',
      position: 'relative',
    }}>
      <div style={{ position: 'absolute', width: 300, height: 300, borderRadius: '50%', background: 'radial-gradient(circle, rgba(179,157,219,0.06) 0%, transparent 70%)', top: -80, right: -60 }} />
      <div style={{ position: 'absolute', width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(144,202,249,0.04) 0%, transparent 70%)', bottom: 40, left: -40 }} />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: 560 }}>
        <Mascot size={80} />
        <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4, letterSpacing: -0.5 }}>小元AI</h1>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 28, fontWeight: 400, letterSpacing: 0.3 }}>数据分析 / 数据采集 / 自动化 / 多智能体协作</p>

        <div style={{ maxWidth: 560, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
          {images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 8, overflowX: 'auto' }}>
              {images.map((img, i) => (
                <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                  <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid var(--border)' }} />
                  <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                    style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: 'var(--danger)', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-input)', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px var(--shadow-sm)'}
            onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
              <textarea value={quickInput} onChange={(e) => { setQuickInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; t.style.overflowY = t.scrollHeight > 200 ? 'auto' : 'hidden' }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && quickInput.trim()) { e.preventDefault(); const v = quickInput.trim(); setQuickInput(''); sendWithNewSession(v) } }}
                placeholder="输入消息..."
                rows={1}
                style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflow: 'hidden' }} />
              <input ref={fileRef} type="file" accept="image/*,.csv,.xlsx,.xls,.json" multiple hidden
                onChange={async (e) => {
                  const files = e.target.files
                  if (!files) return
                  for (const f of Array.from(files)) {
                    const ext = f.name.split('.').pop()?.toLowerCase()
                    if (['csv','xlsx','xls','json'].includes(ext || '')) {
                      try {
                        const result = await uploadDataset(f)
                        setQuickInput((p) => p + ` [数据集 #${result.id}: ${result.name}]`)
                      } catch { /* ignore */ }
                    } else {
                      const reader = new FileReader()
                      reader.onload = () => setImages((p) => [...p, reader.result as string])
                      reader.readAsDataURL(f)
                    }
                  }
                  e.target.value = ''
                }}
              />
              <button onClick={() => fileRef.current?.click()} title="上传文件/图片"
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--text-muted)', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                onMouseLeave={(e) => e.currentTarget.style.opacity = '0.5'}
              >📎</button>
              <button onClick={() => { if (quickInput.trim()) { const v = quickInput.trim(); setQuickInput(''); sendWithNewSession(v) } }} disabled={!quickInput.trim()}
                className="btn btn-primary"
                style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, opacity: !quickInput.trim() ? 0.5 : 1, borderRadius: 10 }}>发送</button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 14px 10px' }}>
              <ModelSelector model={model} onChange={(v) => { setModel(v) }} />
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 20, width: '100%', maxWidth: 520 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 6 }}>
        {SUGGESTIONS.map((s) => (
          <button key={s.text} onClick={() => sendWithNewSession(s.text)}
            style={{
              padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)',
              background: 'var(--bg-input)', cursor: 'pointer', fontSize: 12, color: 'var(--text-primary)',
              display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 1,
              transition: 'all 0.15s', minWidth: 0, flex: '0 0 auto',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.boxShadow = '0 2px 8px var(--shadow-md)' }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none' }}
          >
            <div style={{ fontWeight: 500, fontSize: 12 }}>{s.text}</div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>{s.desc}</div>
          </button>
        ))}
      </div>
      </div>

      {sessions.length > 0 && (
        <div style={{ marginTop: 20, width: '100%', maxWidth: 560 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, paddingLeft: 4, fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>最近对话</div>
          <div style={{ maxHeight: 120, overflowY: 'auto' }}>
          {sessions.slice(0, 10).map((s) => (
            <div key={s.session_id} onClick={() => onSelectSession(s.session_id)}
              className="task-item"
              style={{
                padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 13,
                color: 'var(--text-primary)', marginBottom: 1, background: 'transparent', border: '1px solid transparent',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}
            >{s.title}</div>
          ))}
          </div>
        </div>
      )}
    </div>
  )
}
