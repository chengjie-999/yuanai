import { useRef, useState, useEffect } from 'react'
import { downloadChat } from './helpers'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ReasoningEffort } from './ReasoningSelector'
import ReasoningSelector from './ReasoningSelector'
import { ModelSelector } from '../ModelSelector'
import { compressImage } from './imageUtils'
import { uploadDataset } from '../../api'
import { PaperclipIcon, XIcon } from '../icons'

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, currentSid, sessions, messages, agentKind, model, setModel, effort, setEffort, onStartVoiceCall, entMode, toggleEntMode, chatBackend, setChatBackend, onStop, notice }: {
  input: string; setInput: (v: string | ((p: string) => string)) => void; loading: boolean; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]; messages: ChatMessage[]
  agentKind: 'chat' | 'claude' | 'automation'
  model: string; setModel: (v: string) => void
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  onStartVoiceCall: () => void
  entMode: boolean; toggleEntMode: () => void
  chatBackend: 'auto' | 'cloud' | 'local'; setChatBackend: (v: 'auto' | 'cloud' | 'local') => void
  onStop: () => void
  notice: string
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  // B1 修复（2026-10-26）：发送后 input 置空，textarea 的自动增高样式残留——
  // 重新输入单行才复原；输入为空时立即复位高度
  useEffect(() => {
    if (!input && taRef.current) {
      taRef.current.style.height = 'auto'
      taRef.current.style.overflowY = 'hidden'
    }
  }, [input])
  const [uploading, setUploading] = useState(false)
  // 模式菜单（2026-11-06 用户拍板：工作/娱乐 + 云端/本机两开关收进菜单，输入区不拥挤）
  const [modeMenuOpen, setModeMenuOpen] = useState(false)
  const modeMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!modeMenuOpen) return
    const onDown = (e: MouseEvent) => {
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target as Node)) setModeMenuOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [modeMenuOpen])
  const [uploadType, setUploadType] = useState<'image' | 'dataset'>('image')
  const [uploadErr, setUploadErr] = useState('')
  // B1：本地上传的数据集卡片（名称/行数/列数，可移除）
  const [uploadedDs, setUploadedDs] = useState<{ id: number; name: string; row_count: number; columns: { name: string }[] }[]>([])
  // B1：数据集选择弹层
  const [dsPickerOpen, setDsPickerOpen] = useState(false)
  const [dsList, setDsList] = useState<{ id: number; name: string; row_count: number; file_type: string }[]>([])
  const [dsLoading, setDsLoading] = useState(false)

  /* 统一上传管线（U1 通用体验 2026-10-25）：文件选择/Ctrl+V 粘贴/拖拽三条入口共用 */
  const handleFiles = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    for (const f of files) {
      const ext = f.name.split('.').pop()?.toLowerCase()
      if (['csv', 'xlsx', 'xls', 'json'].includes(ext || '')) {
        // 数据集文件：上传后注入 [数据集 #id] 引用 + 显示数据卡片
        setUploadType('dataset')
        try {
          const result = await uploadDataset(f)
          setUploadedDs((p) => [...p.filter((x) => x.id !== result.id), result])
          setUploadErr('')
          setInput((p) => p + ` [数据集 #${result.id}: ${result.name}]`)
        } catch {
          setUploadErr(`数据集 ${f.name} 上传失败，请重试`)
        }
      } else {
        setUploadType('image')
        try {
          const compressed = await compressImage(f)
          setImages((p) => [...p, compressed])
        } catch {
          // HEIC（iPhone 原片）：浏览器解不了码，原样回传会撞 nginx 20m 上限
          // （P5 移动优化 2026-10-24）——给出明确提示而不是静默塞超限原图
          if (/heic|heif/i.test(f.type) || /\.(heic|heif)$/i.test(f.name)) {
            setUploadErr(`${f.name} 是 HEIC 格式，浏览器不支持——请在相册里转为 JPG 后发送`)
            continue
          }
          const reader = new FileReader()
          reader.onload = () => setImages((p) => [...p, reader.result as string])
          reader.readAsDataURL(f)
        }
      }
    }
    setUploading(false)
  }

  return (
    <div className="chat-input-area" style={{ padding: '12px 24px 20px', borderTop: '1px solid var(--border)' }}>
      <div className="chat-input-inner" style={{ maxWidth: 720, margin: '0 auto', width: '100%', boxShadow: '0 4px 24px var(--shadow-sm)' }}>
        <div style={{ border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-input)', transition: 'box-shadow 0.2s' }}
          onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 16px var(--shadow-sm)'}
          onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); handleFiles(Array.from(e.dataTransfer.files || [])) }}
        >
          {uploading && (
            <div style={{ fontSize: 12, color: 'var(--accent)', padding: '8px 12px 0', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              {uploadType === 'dataset' ? '正在上传数据集…' : '正在压缩图片…'}
            </div>
          )}
          {uploadErr && (
            <div style={{ fontSize: 12, color: 'var(--danger)', padding: '8px 12px 0' }}>{uploadErr}</div>
          )}
          {/* B1：已上传数据集卡片（名称/行数/列数，可移除） */}
          {uploadedDs.length > 0 && (
            <div style={{ display: 'flex', gap: 6, padding: '8px 12px 0', overflowX: 'auto', flexWrap: 'wrap' }}>
              {uploadedDs.map((ds) => (
                <div key={ds.id} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 8px 4px 10px',
                  borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-primary)',
                  fontSize: 11, color: 'var(--text-secondary)', flexShrink: 0,
                }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ds.name}</span>
                  <span>{ds.row_count} 行 · {ds.columns?.length || 0} 列</span>
                  <span onClick={() => setUploadedDs((p) => p.filter((x) => x.id !== ds.id))}
                    title="移除" aria-label={`移除数据集 ${ds.name}`}
                    style={{ cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2 }}>
                    <XIcon size={10} />
                  </span>
                </div>
              ))}
            </div>
          )}
          {images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, padding: '8px 12px 0', overflowX: 'auto' }}>
              {images.map((img, i) => (
                <div key={i} style={{ position: 'relative', flexShrink: 0 }}>
                  <img src={img} style={{ height: 50, borderRadius: 6, border: '1px solid var(--border)' }} />
                  <span onClick={() => setImages((p) => p.filter((_, j) => j !== i))} title="移除"
                    style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: 'var(--danger)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                    <XIcon size={10} />
                  </span>
                </div>
              ))}
            </div>
          )}
          {/* 输入行：只留输入框 + 发送/停止（豆包式，功能键全部下沉工具行）；
              P1-2：loading 时输入框不锁（可继续打字），发送键变停止键 */}
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
            <textarea ref={taRef} value={input} onChange={(e) => { setInput(e.target.value); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; t.style.overflowY = t.scrollHeight > 200 ? 'auto' : 'hidden' }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (loading) { onStop() } else { handleSend() } }
              }}
              onPaste={(e) => {
                // U1：Ctrl+V 粘贴图片/截图（通用 AI 对话方案）
                const items = e.clipboardData?.items
                if (!items) return
                const files = Array.from(items)
                  .filter((i) => i.kind === 'file')
                  .map((i) => i.getAsFile())
                  .filter((f): f is File => !!f)
                if (files.length) { e.preventDefault(); handleFiles(files) }
              }}
              placeholder={entMode ? '想聊点什么？八卦、脑洞、安利都行~'
                : agentKind === 'claude' ? '向 Claude Code 下达任务…'
                : agentKind === 'automation' ? '向自动化 Agent 下达任务…'
                : '输入消息...'}
              rows={1}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflow: 'hidden', color: 'var(--text-primary)' }}
            />
            {loading ? (
              <button onClick={onStop} title="停止生成" aria-label="停止生成"
                style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, borderRadius: 10, border: '1px solid var(--danger)', background: 'transparent', color: 'var(--danger)', cursor: 'pointer' }}
              >停止</button>
            ) : (
              <button onClick={() => handleSend()} disabled={!input.trim() || !currentSid}
                className="btn btn-primary"
                style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, borderRadius: 10, opacity: !input.trim() || !currentSid ? 0.5 : 1 }}
              >发送</button>
            )}
          </div>
          {notice && (
            <div style={{ padding: '0 16px 6px', fontSize: 12, color: 'var(--accent)' }}>{notice}</div>
          )}
          {/* 工具行：左侧动作群（@指定/图片/语音/朗读/下载），右侧设置群（模式/推理强度） */}
          <div className="chat-tool-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '0 14px 10px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <input ref={fileRef} type="file" accept="image/*,.csv,.xlsx,.xls,.json" multiple hidden
                onChange={(e) => {
                  if (e.target.files) handleFiles(Array.from(e.target.files))
                  e.target.value = ''
                }}
              />
              {/* @ 面板已移除（2026-11-13 多窗口 v2 用户拍板「小元里怎么还有艾特」）：
                  智能体切换走侧边栏切换器；从主对话派活由统筹自主委派（delegate 工具），
                  或切到该智能体执行窗口直接下达 */}
              <button onClick={() => fileRef.current?.click()} className="yuan-tip" data-tip="上传图片或数据集" aria-label="上传图片或数据集"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
              ><PaperclipIcon size={17} /></button>
              {/* B1：数据集选择弹层（历史数据集一键注入 [数据集 #id]） */}
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <button onClick={() => {
                  if (!dsPickerOpen) {
                    setDsLoading(true)
                    import('../../api').then(({ fetchDatasets }) => fetchDatasets()
                      .then((list: any[]) => { setDsList(Array.isArray(list) ? list : []); setDsLoading(false) })
                      .catch(() => setDsLoading(false)))
                  }
                  setDsPickerOpen((o) => !o)
                }} className="yuan-tip" data-tip="选择数据集" aria-label="选择数据集"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
                >
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <ellipse cx="12" cy="5" rx="9" ry="3" />
                    <path d="M3 5v14a9 3 0 0 0 18 0V5" />
                    <path d="M3 12a9 3 0 0 0 18 0" />
                  </svg>
                </button>
                {dsPickerOpen && (
                  <>
                    <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setDsPickerOpen(false)} />
                    <div style={{
                      position: 'absolute', bottom: 'calc(100% + 8px)', left: 0, zIndex: 41,
                      minWidth: 260, maxWidth: '78vw', maxHeight: 280, overflowY: 'auto',
                      background: 'var(--bg-primary)', border: '1px solid var(--border)',
                      borderRadius: 10, boxShadow: '0 8px 28px var(--shadow-md)', padding: 6, textAlign: 'left',
                    }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 8px 6px', fontWeight: 600 }}>
                        选择数据集（点击注入引用）
                      </div>
                      {dsLoading ? (
                        <div style={{ padding: '12px 8px', fontSize: 12, color: 'var(--text-muted)' }}>加载中…</div>
                      ) : dsList.length === 0 ? (
                        <div style={{ padding: '12px 8px', fontSize: 12, color: 'var(--text-muted)' }}>暂无数据集，用回形针上传</div>
                      ) : dsList.map((ds) => (
                        <div key={ds.id}
                          onClick={() => {
                            setInput((p) => p + ` [数据集 #${ds.id}: ${ds.name}]`)
                            setDsPickerOpen(false)
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--hover-bg)' }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                          style={{
                            padding: '7px 8px', borderRadius: 7, cursor: 'pointer', fontSize: 12,
                            color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8,
                          }}>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{ds.name}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{ds.row_count} 行</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
              {/* 多窗口 P2：语音仅对话窗口——执行窗口是任务下发，无语音通话 */}
              {agentKind === 'chat' && (
              <button onClick={onStartVoiceCall} className="yuan-tip" data-tip="语音通话" aria-label="语音通话"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
              </button>
              )}
              <button onClick={() => {
                const s = sessions.find(s => s.session_id === currentSid)
                downloadChat(messages, `${s?.title || 'chat'}.txt`)
              }} className="yuan-tip chat-tool-download" data-tip="下载聊天记录" aria-label="下载聊天记录"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {/* 模式菜单（2026-11-06 用户拍板：工作/娱乐 + 云端/本机收进菜单，
                  输入区按钮不拥挤——按钮显示当前模式摘要，点击展开） */}
              <div ref={modeMenuRef} style={{ position: 'relative', flexShrink: 0 }}>
                <button onClick={() => setModeMenuOpen((o) => !o)}
                  aria-label="对话模式与执行位置"
                  className="yuan-tip" data-tip="对话模式与执行位置"
                  style={{ border: '1px solid var(--border)', borderRadius: 999, background: 'none',
                    cursor: 'pointer', padding: '3px 10px', fontSize: 12, fontWeight: 600,
                    color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  {entMode ? '娱乐' : '工作'}·{entMode ? '云端' : (chatBackend === 'auto' ? '自动' : chatBackend === 'cloud' ? '云端' : '本机')}
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </button>
                {modeMenuOpen && (
                  <div style={{ position: 'absolute', bottom: 'calc(100% + 8px)', left: 0, zIndex: 30,
                    background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 10,
                    boxShadow: 'var(--shadow-md)', padding: '12px 14px', minWidth: 190, fontSize: 12.5 }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>对话模式</div>
                    <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 999,
                      overflow: 'hidden', marginBottom: 12 }}>
                      <button onClick={() => { if (entMode) toggleEntMode(); setModeMenuOpen(false) }} aria-label="工作模式"
                        style={{ flex: 1, border: 'none', cursor: entMode ? 'pointer' : 'default', padding: '5px 0', fontWeight: 600,
                          background: entMode ? 'transparent' : 'var(--accent-light)', color: entMode ? 'var(--text-secondary)' : 'var(--accent)', transition: 'all 0.15s' }}>
                        工作
                      </button>
                      <button onClick={() => { if (!entMode) toggleEntMode(); setModeMenuOpen(false) }} aria-label="娱乐模式"
                        style={{ flex: 1, border: 'none', cursor: entMode ? 'default' : 'pointer', padding: '5px 0', fontWeight: 600,
                          background: entMode ? 'var(--accent-light)' : 'transparent', color: entMode ? 'var(--accent)' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
                        娱乐
                      </button>
                    </div>
                    <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                      执行位置{entMode && <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（娱乐模式固定云端）</span>}
                    </div>
                    <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 999,
                      overflow: 'hidden', opacity: entMode ? 0.5 : 1 }}>
                      {(['cloud', 'auto', 'local'] as const).map((b) => (
                        <button key={b} onClick={() => { if (!entMode) { setChatBackend(b); setModeMenuOpen(false) } }}
                          aria-label={b === 'cloud' ? '云端' : b === 'auto' ? '自动' : '本机'}
                          style={{ flex: 1, border: 'none', cursor: entMode ? 'default' : 'pointer', padding: '5px 0', fontWeight: 600,
                            background: (!entMode && chatBackend === b) ? 'var(--accent-light)' : 'transparent',
                            color: (!entMode && chatBackend === b) ? 'var(--accent)' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
                          {b === 'cloud' ? '云端' : b === 'auto' ? '自动' : '本机'}
                        </button>
                      ))}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                      自动：本机优先，离线回退云端；云端：不走本机 Agent；本机：强制本机（离线报错）
                    </div>
                  </div>
                )}
              </div>
              <ModelSelector model={model} onChange={setModel} />
              <ReasoningSelector effort={effort} setEffort={setEffort} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
