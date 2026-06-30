import { useRef } from 'react'
import { ModelSelector } from '../ModelSelector'
import { SUGGESTIONS } from '../../config/agents'
import { uploadDataset } from '../../api'
import { useTheme } from '../../contexts/ThemeContext'
import type { SessionInfo } from './helpers'

export default function WelcomePage({ images, setImages, quickInput, setQuickInput, sendWithNewSession, model, setModel, sessions, onSelectSession }: {
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  quickInput: string; setQuickInput: (v: string | ((p: string) => string)) => void
  sendWithNewSession: (text: string) => void
  model: string; setModel: (v: string) => void
  sessions: SessionInfo[]; onSelectSession: (sid: string) => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const { isDark } = useTheme()

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
        <div style={{ position: 'relative', width: 80, height: 80, marginBottom: 16, animation: isDark ? 'float 5s ease-in-out infinite' : 'float 3s ease-in-out infinite' }}>
          {isDark ? (
            <svg viewBox="0 0 100 100" width={80} height={80}>
              {/* Stars */}
              <circle cx="15" cy="20" r="1" fill="#90a4ae" opacity="0.35">
                <animate attributeName="opacity" values="0.35;0.1;0.35" dur="3s" repeatCount="indefinite" />
              </circle>
              <circle cx="85" cy="16" r="1.2" fill="#90a4ae" opacity="0.3">
                <animate attributeName="opacity" values="0.3;0.55;0.3" dur="2.5s" repeatCount="indefinite" />
              </circle>
              <circle cx="8" cy="62" r="0.8" fill="#90a4ae" opacity="0.25">
                <animate attributeName="opacity" values="0.25;0.5;0.25" dur="3.5s" repeatCount="indefinite" />
              </circle>
              <circle cx="92" cy="72" r="1" fill="#90a4ae" opacity="0.3">
                <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2.8s" repeatCount="indefinite" />
              </circle>
              {/* Outer glow — warm night */}
              <circle cx="50" cy="50" r="45" fill="#b39ddb" opacity="0.04" />
              {/* Headphones — band */}
              <path d="M22 40 Q22 12 50 10 Q78 12 78 40" fill="none" stroke="#546e7a" strokeWidth="5" strokeLinecap="round" />
              {/* Headphones — ear cups */}
              <rect x="14" y="36" rx="4" ry="4" width="12" height="22" fill="#3d4a52" />
              <rect x="74" y="36" rx="4" ry="4" width="12" height="22" fill="#3d4a52" />
              <rect x="16" y="38" rx="2" ry="2" width="8" height="18" fill="#4d5a62" />
              <rect x="76" y="38" rx="2" ry="2" width="8" height="18" fill="#4d5a62" />
              {/* Head */}
              <circle cx="50" cy="52" r="32" fill="#3d4a52" />
              <circle cx="50" cy="52" r="27" fill="#4d5a62" />
              {/* Orbiting dots — dim stars */}
              {[[14,32],[86,32],[22,74],[78,74]].map(([x,y],i)=>(
                <g key={i}>
                  <line x1={i<2?28:36} y1={i<2?42:60} x2={x} y2={y} stroke="#5a6a74" strokeWidth="3" strokeLinecap="round" />
                  <circle cx={x} cy={y} r="4.5" fill="#90a4ae">
                    <animate attributeName="opacity" values="0.35;0.6;0.35" dur={`${2.5+i*0.4}s`} repeatCount="indefinite" />
                  </circle>
                </g>
              ))}
              {/* Sleep mask — soft dark fabric */}
              <path d="M22 44 Q50 38 78 44 Q79 50 50 48 Q21 50 22 44Z" fill="#382844" />
              {/* Mask top edge highlight (fabric fold) */}
              <path d="M22 44 Q50 38 78 44" fill="none" stroke="#4a3858" strokeWidth="1.5" strokeLinecap="round" />
              {/* Mask lower edge shadow */}
              <path d="M22 47 Q50 50 78 47" fill="none" stroke="#2a1c34" strokeWidth="0.8" opacity="0.5" />
              {/* Mask straps — darker thin lines */}
              <path d="M22 45 L14 41" stroke="#4a3858" strokeWidth="2" strokeLinecap="round" opacity="0.7" />
              <path d="M78 45 L86 41" stroke="#4a3858" strokeWidth="2" strokeLinecap="round" opacity="0.7" />
              {/* Gentle smile — warm */}
              <path d="M43 64 Q50 69 57 64" fill="none" stroke="#90a4ae" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
              {/* Blush — soft warm pink, peeks under mask */}
              <ellipse cx="28" cy="55" rx="5" ry="4" fill="#f48fb1" opacity="0.16" />
              <ellipse cx="72" cy="55" rx="5" ry="4" fill="#f48fb1" opacity="0.16" />
              {/* Zzz — staggered floating, lavender-mint */}
              <g opacity="0">
                <animate attributeName="opacity" values="0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
                <animateTransform attributeName="transform" type="translate" values="4,4;4,-2;4,-8;4,-8;4,-2" dur="4s" repeatCount="indefinite" />
                <text x="62" y="26" fill="#4db6ac" fontSize="12" fontWeight="bold" fontFamily="sans-serif">z</text>
              </g>
              <g opacity="0">
                <animate attributeName="opacity" values="0;0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
                <animateTransform attributeName="transform" type="translate" values="8,8;8,2;8,-2;8,-8;8,-8;8,-2" dur="4s" repeatCount="indefinite" />
                <text x="68" y="20" fill="#4db6ac" fontSize="16" fontWeight="bold" fontFamily="sans-serif">Z</text>
              </g>
              <g opacity="0">
                <animate attributeName="opacity" values="0;0;0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
                <animateTransform attributeName="transform" type="translate" values="12,12;12,6;12,2;12,-2;12,-8;12,-8;12,-2" dur="4s" repeatCount="indefinite" />
                <text x="76" y="14" fill="#4db6ac" fontSize="20" fontWeight="bold" fontFamily="sans-serif">Z</text>
              </g>
            </svg>
          ) : (
            <svg viewBox="0 0 100 100" width={80} height={80}>
              <circle cx="50" cy="50" r="42" fill="#42a5f5" opacity="0.08" />
              <circle cx="50" cy="52" r="32" fill="#1976d2" />
              <circle cx="50" cy="52" r="27" fill="#42a5f5" />
              {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
                <g key={i}>
                  <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#1976d2" strokeWidth="5" strokeLinecap="round" />
                  <circle cx={x} cy={y} r="6" fill="#90caf9" />
                </g>
              ))}
              <ellipse cx="38" cy="44" rx="7" ry="8" fill="#fff" />
              <ellipse cx="38" cy="44" rx="4" ry="5" fill="#311b92" />
              <circle cx="40" cy="42" r="2" fill="#fff" opacity="0.9" />
              <path d="M53 44 Q59 38 65 44" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0">
                <animate attributeName="opacity" values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;1;0" dur="4s" repeatCount="indefinite" />
              </path>
              <ellipse cx="59" cy="44" rx="7" ry="8" fill="#fff">
                <animate attributeName="ry" values="8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;3;1;8" dur="4s" repeatCount="indefinite" />
              </ellipse>
              <ellipse cx="59" cy="44" rx="4" ry="5" fill="#0d47a1">
                <animate attributeName="ry" values="5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;1.5;0.5;5" dur="4s" repeatCount="indefinite" />
              </ellipse>
              <circle cx="61" cy="42" r="2" fill="#fff" opacity="0.9">
                <animate attributeName="opacity" values="0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0;0;0.9" dur="4s" repeatCount="indefinite" />
              </circle>
              <path d="M42 60 Q50 70 58 60" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0.85" />
              <ellipse cx="30" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
              <ellipse cx="70" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
            </svg>
          )}
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4, letterSpacing: -0.5 }}>小元AI</h1>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 28, fontWeight: 400, letterSpacing: 0.3 }}>数据分析 / 数据采集 / 自动化 / 多智能体协作</p>

        <div style={{ maxWidth: 560, width: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.06)' }}>
          {images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 8, overflowX: 'auto' }}>
              {images.map((img, i) => (
                <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                  <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid var(--border)' }} />
                  <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))}
                    style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: '#e53935', color: '#fff', fontSize: 12, lineHeight: '18px', textAlign: 'center', cursor: 'pointer' }}>✕</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-input)', transition: 'box-shadow 0.2s' }}
            onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px var(--shadow-sm)'}
            onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
          >
            <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
              <textarea value={quickInput} onChange={(e) => { setQuickInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px' }}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && quickInput.trim()) { e.preventDefault(); const v = quickInput.trim(); setQuickInput(''); sendWithNewSession(v) } }}
                placeholder="输入消息，开始对话... (Enter 发送，Shift+Enter 换行)"
                rows={1}
                style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflowY: 'auto' }} />
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
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#999', padding: '8px', lineHeight: 1, opacity: 0.5, transition: 'opacity 0.15s' }}
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
