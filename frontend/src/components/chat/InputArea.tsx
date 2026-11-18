import { useRef, useState, useEffect } from 'react'
import { downloadChat } from './helpers'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import { compressImage } from './imageUtils'
import { uploadDataset } from '../../api'
import { PaperclipIcon, XIcon } from '../icons'

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, currentSid, sessions, messages, agentKind, onStartVoiceCall, entMode, toggleEntMode, onOpenSettings, onStop, notice }: {
  input: string; setInput: (v: string | ((p: string) => string)) => void; loading: boolean; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]; messages: ChatMessage[]
  agentKind: 'chat' | 'claude' | 'automation'
  onStartVoiceCall: () => void
  onOpenSettings: () => void
  entMode: boolean; toggleEntMode: () => void
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
  // T14 P1-2（2026-11-17）：iOS Safari 键盘弹起时页面不重排、输入区可能被键盘
  // 遮住——监听 visualViewport 收缩（高度骤减 >15% = 键盘弹出），把聚焦的
  // 输入框滚进可视区兜底（安卓键盘会压缩视口，走浏览器默认行为即可）
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const onResize = () => {
      if (window.innerWidth > 768) return
      if (vv.height < window.innerHeight * 0.85
        && document.activeElement?.tagName === 'TEXTAREA') {
        requestAnimationFrame(() => {
          ;(document.activeElement as HTMLElement | null)
            ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        })
      }
    }
    vv.addEventListener('resize', onResize)
    return () => vv.removeEventListener('resize', onResize)
  }, [])
  // 切换即时反馈（方案 C1）：任何设置切换 → 提示条 2s 消失
  const [tip, setTip] = useState('')
  const tipTimerRef = useRef<number | null>(null)
  const flashTip = (text: string) => {
    setTip(text)
    if (tipTimerRef.current) window.clearTimeout(tipTimerRef.current)
    tipTimerRef.current = window.setTimeout(() => setTip(''), 2000)
  }
  const [uploadType, setUploadType] = useState<'image' | 'dataset'>('image')
  const [uploadErr, setUploadErr] = useState('')
  // B1：本地上传的数据集卡片（名称/行数/列数，可移除）
  const [uploadedDs, setUploadedDs] = useState<{ id: number; name: string; row_count: number; columns: { name: string }[] }[]>([])

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
                // T16 批次 2（2026-11-18）：生成中 Enter = 排队自动发送
                // （handleSend 内部排队）；「停止」按钮保留显式停止
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
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
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 16, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflow: 'hidden', color: 'var(--text-primary)' }}
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
          {tip && (
            <div style={{ padding: '0 16px 6px', fontSize: 12, color: 'var(--accent)' }}>{tip}</div>
          )}
          {/* 工具行：左侧动作群（图片/语音/下载），右侧工作·娱乐 + 任务设置（2026-11-14 重构） */}
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
              <button onClick={() => fileRef.current?.click()} className="yuan-tip chat-tool-icon-btn" data-tip="上传图片或数据集" aria-label="上传图片或数据集"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
              ><PaperclipIcon size={17} /></button>
              {/* 多窗口 P2：语音仅对话窗口——执行窗口是任务下发，无语音通话 */}
              {agentKind === 'chat' && (
              <button onClick={onStartVoiceCall} className="yuan-tip chat-tool-icon-btn" data-tip="语音通话" aria-label="语音通话"
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
              }} className="yuan-tip chat-tool-download chat-tool-icon-btn" data-tip="下载聊天记录" aria-label="下载聊天记录"
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
                                                        {/* 工具行右侧（2026-11-14 用户拍板「都用子页面」）：只留工作/娱乐
                  两字分段 + 设置齿轮（打开设置页浮窗——模型/推理强度/执行位置/
                  数据集全部子页面化，输入区不再堆设置） */}
              {agentKind === 'chat' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 999, overflow: 'hidden' }}>
                  <button onClick={() => { if (entMode) { toggleEntMode(); flashTip('已切换：工作模式') } }} aria-label="工作模式"
                    style={{ border: 'none', cursor: 'pointer', padding: '4px 12px', fontSize: 12, fontWeight: 600,
                      background: entMode ? 'transparent' : 'var(--accent-light)', color: entMode ? 'var(--text-secondary)' : 'var(--accent)', transition: 'all 0.15s' }}>
                    工作
                  </button>
                  <button onClick={() => { if (!entMode) { toggleEntMode(); flashTip('已切换：娱乐模式（云端直达）') } }} aria-label="娱乐模式"
                    style={{ border: 'none', cursor: 'pointer', padding: '4px 12px', fontSize: 12, fontWeight: 600,
                      background: entMode ? 'var(--accent-light)' : 'transparent', color: entMode ? 'var(--accent)' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
                    娱乐
                  </button>
                </div>
                <button onClick={onOpenSettings} aria-label="对话设置"
                  className="yuan-tip" data-tip="对话设置（模型 / 推理强度 / 执行位置 / 数据集）"
                  style={{ border: '1px solid var(--border)', borderRadius: 999, background: 'none',
                    cursor: 'pointer', padding: '4px 10px', color: 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', gap: 4 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </button>
              </div>
              )}
              {/* 执行窗口（CC/自动化）右侧：只读「本机执行」徽标（借鉴 Cursor 每视图
                  有明确状态标识；模型由 Agent 端固定——CC 走桥接配置、自动化固定
                  豆包 pro，网页端不提供选择避免误导） */}
              {agentKind !== 'chat' && (
                <span title="执行窗口固定在本机 Agent 执行（模型由 Agent 端配置）" aria-label="本机执行"
                  style={{ fontSize: 11.5, padding: '3px 10px', borderRadius: 999,
                    border: '1px solid var(--border)', color: 'var(--text-muted)',
                    display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', flexShrink: 0 }} />
                  本机执行
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
