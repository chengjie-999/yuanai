import { useRef, useState, useEffect } from 'react'
import { downloadChat } from './helpers'
import type { ChatMessage } from '../../types'
import type { SessionInfo } from './helpers'
import type { ReasoningEffort } from './ReasoningSelector'
import ReasoningSelector from './ReasoningSelector'
import { ModelSelector } from '../ModelSelector'
import { compressImage } from './imageUtils'
import { AGENT_CONFIG } from '../../config/agents'
import { uploadDataset } from '../../api'
import { PaperclipIcon, XIcon, AtSignIcon } from '../icons'

// @指定智能体候选（融合后：分析/采集已是统筹内置工具，不再单独指定）
const TARGET_AGENTS = [
  { key: 'orchestrator', desc: '统筹亲自回答（内置分析/采集脚本工具）' },
  { key: 'automation', desc: '浏览器控制、审核、截图' },
  { key: 'claude', desc: '本机代码、终端、Git 任务' },
]

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, currentSid, sessions, messages, localOnline, claudeOnline, model, setModel, effort, setEffort, onStartVoiceCall, entMode, toggleEntMode, chatBackend, setChatBackend, targetAgent, setTargetAgent, onOpenDirectChat, onStop, notice }: {
  input: string; setInput: (v: string | ((p: string) => string)) => void; loading: boolean; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]; messages: ChatMessage[]
  model: string; setModel: (v: string) => void
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  localOnline: boolean; claudeOnline: boolean
  onStartVoiceCall: () => void
  entMode: boolean; toggleEntMode: () => void
  chatBackend: 'auto' | 'cloud' | 'local'; setChatBackend: (v: 'auto' | 'cloud' | 'local') => void
  targetAgent: string; setTargetAgent: (v: string) => void
  onOpenDirectChat: (target: string) => void
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
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickIndex, setPickIndex] = useState(0)
  // B1：本地上传的数据集卡片（名称/行数/列数，可移除）
  const [uploadedDs, setUploadedDs] = useState<{ id: number; name: string; row_count: number; columns: { name: string }[] }[]>([])
  // B1：数据集选择弹层
  const [dsPickerOpen, setDsPickerOpen] = useState(false)
  const [dsList, setDsList] = useState<{ id: number; name: string; row_count: number; file_type: string }[]>([])
  const [dsLoading, setDsLoading] = useState(false)

  // 选中 @ 候选：设定定向 + 移除输入框里残留的裸 @（及其后的半截文字）
  const selectTarget = (key: string) => {
    setTargetAgent(key)
    setPickerOpen(false)
    setPickIndex(0)
    const idx = input.lastIndexOf('@')
    if (idx >= 0) setInput((p) => p.slice(0, idx).trimEnd())
  }

  // @ 面板可用候选（按 @ 后已输入串过滤）
  const atQuery = pickerOpen ? input.slice(input.lastIndexOf('@') + 1).trim().toLowerCase() : ''
  const filteredAgents = TARGET_AGENTS.filter((a) => {
    if (!atQuery) return true
    const cfg = AGENT_CONFIG[a.key]
    return a.key.includes(atQuery) || cfg.label.toLowerCase().includes(atQuery)
      || a.desc.toLowerCase().includes(atQuery)
  })

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
          {targetAgent && AGENT_CONFIG[targetAgent] && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px 0', flexWrap: 'wrap' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 6px 3px 8px',
                borderRadius: 999, border: `1px solid ${AGENT_CONFIG[targetAgent].color}55`,
                background: AGENT_CONFIG[targetAgent].bg, fontSize: 12, fontWeight: 600,
                color: AGENT_CONFIG[targetAgent].color, lineHeight: 1,
              }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: AGENT_CONFIG[targetAgent].color, flexShrink: 0 }} />
                @{AGENT_CONFIG[targetAgent].label}
                <span onClick={() => setTargetAgent('')} className="yuan-tip" data-tip="取消指定" aria-label="取消指定"
                  style={{ cursor: 'pointer', padding: '1px 2px', opacity: 0.7, display: 'flex', alignItems: 'center' }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
                ><XIcon size={11} /></span>
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>本条消息将定向该智能体处理</span>
            </div>
          )}
          {/* 输入行：只留输入框 + 发送/停止（豆包式，功能键全部下沉工具行）；
              P1-2：loading 时输入框不锁（可继续打字），发送键变停止键 */}
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
            <textarea ref={taRef} value={input} onChange={(e) => { setInput(e.target.value); if (!pickerOpen && e.target.value.endsWith('@')) { setPickerOpen(true); setPickIndex(0) }; const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; t.style.overflowY = t.scrollHeight > 200 ? 'auto' : 'hidden' }}
              onKeyDown={(e) => {
                // @面板键盘导航：↑↓ 移动 / Enter 选中 / Esc 关闭
                if (pickerOpen) {
                  if (e.key === 'ArrowDown') { e.preventDefault(); setPickIndex((i) => Math.min(i + 1, filteredAgents.length - 1)); return }
                  if (e.key === 'ArrowUp') { e.preventDefault(); setPickIndex((i) => Math.max(i - 1, 0)); return }
                  if (e.key === 'Enter') { e.preventDefault(); const a = filteredAgents[pickIndex]; if (a && !(a.key === 'automation' && !localOnline) && !(a.key === 'claude' && !claudeOnline)) selectTarget(a.key); return }
                  if (e.key === 'Escape') { e.preventDefault(); setPickerOpen(false); return }
                }
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
              placeholder={entMode ? '想聊点什么？八卦、脑洞、安利都行~' : '输入消息，@ 可指定智能体...'}
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
              {/* @ 面板与按钮为兄弟节点：面板点击不冒泡回按钮（曾因冒泡 toggle 导致面板关不掉）；
                  娱乐模式不委派——隐藏 @ 入口 */}
              {!entMode && (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <button onClick={() => setPickerOpen((o) => !o)} className="yuan-tip"
                  data-tip={targetAgent ? `已指定：${AGENT_CONFIG[targetAgent]?.label || ''}` : '指定智能体回答'} aria-label="指定智能体"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: targetAgent ? 'var(--accent)' : 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: targetAgent ? 1 : 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = targetAgent ? '1' : '0.7' }}
                >
                  <AtSignIcon size={17} />
                </button>
                {pickerOpen && (
                  <>
                    <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setPickerOpen(false)} />
                    <div style={{
                      position: 'absolute', bottom: 'calc(100% + 8px)', left: 0, zIndex: 41,
                      minWidth: 210, background: 'var(--bg-primary)', border: '1px solid var(--border)',
                      borderRadius: 10, boxShadow: '0 8px 28px var(--shadow-md)', padding: 6, textAlign: 'left',
                    }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 8px 6px', fontWeight: 600 }}>
                        @指定智能体处理本条消息
                      </div>
                      {filteredAgents.length === 0 && (
                        <div style={{ padding: '8px', fontSize: 12, color: 'var(--text-muted)' }}>无匹配的智能体</div>
                      )}
                      {filteredAgents.map((a, ai) => {
                        const cfg = AGENT_CONFIG[a.key]
                        const active = targetAgent === a.key
                        // 群聊规则：本地 Agent 离线时子智能体不可 @（不做云端角色冒充）；
                        // @Claude Code 需桥接在线；@统筹 永远可用（云端小元AI）
                        const available = a.key === 'orchestrator'
                          ? true
                          : a.key === 'claude' ? claudeOnline : localOnline
                        // 长任务小窗：claude/automation 可开独立会话（不占主对话 60 条截断）
                        const canDirect = available && a.key !== 'orchestrator'
                        const highlighted = ai === pickIndex
                        return (
                          <div key={a.key}
                            onClick={() => { if (!available) return; selectTarget(a.key) }}
                            onMouseEnter={(e) => { if (available) { e.currentTarget.style.background = 'var(--hover-bg)'; setPickIndex(ai) } }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = (active || highlighted) ? 'var(--hover-bg)' : 'transparent' }}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px',
                              borderRadius: 7, cursor: available ? 'pointer' : 'not-allowed',
                              fontSize: 13, opacity: available ? 1 : 0.45,
                              color: 'var(--text-primary)',
                              background: (active || highlighted) ? 'var(--hover-bg)' : 'transparent',
                            }}>
                            <span style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
                            <span style={{ fontWeight: 600, color: cfg.color }}>{cfg.label}</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1, textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {available ? a.desc : '离线'}
                            </span>
                            {canDirect && (
                              <span onClick={(e) => { e.stopPropagation(); setPickerOpen(false); onOpenDirectChat(a.key) }}
                                className="yuan-tip" data-tip="开小窗：独立会话与该智能体长任务对话（不占主对话历史）"
                                aria-label={`与 ${cfg.label} 开小窗`}
                                style={{ fontSize: 11, color: 'var(--accent)', padding: '2px 8px', borderRadius: 999, border: '1px solid var(--accent)', cursor: 'pointer', flexShrink: 0 }}
                                onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--accent)'; e.currentTarget.style.color = '#fff' }}
                                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--accent)' }}
                              >小窗</span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </>
                )}
              </div>
              )}
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
