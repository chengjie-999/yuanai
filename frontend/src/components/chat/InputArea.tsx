import { useRef, useState } from 'react'
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

export default function InputArea({ input, setInput, loading, handleSend, images, setImages, currentSid, sessions, messages, localOnline, claudeOnline, model, setModel, effort, setEffort, onStartVoiceCall, targetAgent, setTargetAgent, onOpenDirectChat }: {
  input: string; setInput: (v: string | ((p: string) => string)) => void; loading: boolean; handleSend: (textOverride?: string) => void
  images: string[]; setImages: (v: string[] | ((p: string[]) => string[])) => void
  currentSid: string
  sessions: SessionInfo[]; messages: ChatMessage[]
  model: string; setModel: (v: string) => void
  effort: ReasoningEffort; setEffort: (v: ReasoningEffort) => void
  localOnline: boolean; claudeOnline: boolean
  onStartVoiceCall: () => void
  targetAgent: string; setTargetAgent: (v: string) => void
  onOpenDirectChat: (target: string) => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)

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
          {/* 输入行：只留输入框 + 发送（豆包式，功能键全部下沉工具行） */}
          <div style={{ display: 'flex', alignItems: 'flex-end', padding: '4px 4px 4px 16px' }}>
            <textarea value={input} onChange={(e) => { setInput(e.target.value); if (!pickerOpen && e.target.value.endsWith('@')) setPickerOpen(true); const t = e.target; t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 200) + 'px'; t.style.overflowY = t.scrollHeight > 200 ? 'auto' : 'hidden' }}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="输入消息，@ 可指定智能体..." disabled={loading}
              rows={1}
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: 14, fontFamily: 'inherit', padding: '12px 0', background: 'transparent', resize: 'none', maxHeight: 200, overflow: 'hidden', color: 'var(--text-primary)' }}
            />
            <button onClick={() => handleSend()} disabled={loading || !input.trim() || !currentSid}
              className="btn btn-primary"
              style={{ padding: '10px 24px', fontSize: 14, fontWeight: 600, borderRadius: 10, opacity: loading || !input.trim() || !currentSid ? 0.5 : 1 }}
            >{loading ? '...' : '发送'}</button>
          </div>
          {/* 工具行：左侧动作群（@指定/图片/语音/朗读/下载），右侧设置群（模式/推理强度） */}
          <div className="chat-tool-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '0 14px 10px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <input ref={fileRef} type="file" accept="image/*,.csv,.xlsx,.xls,.json" multiple hidden
                onChange={async (e) => {
                  const files = e.target.files
                  if (!files) return
                  setUploading(true)
                  for (const f of Array.from(files)) {
                    const ext = f.name.split('.').pop()?.toLowerCase()
                    if (['csv', 'xlsx', 'xls', 'json'].includes(ext || '')) {
                      // 数据集文件：上传后以 [数据集 #id] 引用注入输入框（原欢迎页入口）
                      try {
                        const result = await uploadDataset(f)
                        setInput((p) => p + ` [数据集 #${result.id}: ${result.name}]`)
                      } catch { /* ignore */ }
                    } else {
                      try {
                        const compressed = await compressImage(f)
                        setImages((p) => [...p, compressed])
                      } catch {
                        const reader = new FileReader()
                        reader.onload = () => setImages((p) => [...p, reader.result as string])
                        reader.readAsDataURL(f)
                      }
                    }
                  }
                  setUploading(false)
                  e.target.value = ''
                }}
              />
              {/* @ 面板与按钮为兄弟节点：面板点击不冒泡回按钮（曾因冒泡 toggle 导致面板关不掉） */}
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
                      {TARGET_AGENTS.map((a) => {
                        const cfg = AGENT_CONFIG[a.key]
                        const active = targetAgent === a.key
                        // 群聊规则：本地 Agent 离线时子智能体不可 @（不做云端角色冒充）；
                        // @Claude Code 需桥接在线；@统筹 永远可用（云端小元AI）
                        const available = a.key === 'orchestrator'
                          ? true
                          : a.key === 'claude' ? claudeOnline : localOnline
                        // 长任务小窗：claude/automation 可开独立会话（不占主对话 60 条截断）
                        const canDirect = available && a.key !== 'orchestrator'
                        return (
                          <div key={a.key}
                            onClick={() => { if (!available) return; setTargetAgent(a.key); setPickerOpen(false) }}
                            onMouseEnter={(e) => { if (available) e.currentTarget.style.background = 'var(--hover-bg)' }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = active ? 'var(--hover-bg)' : 'transparent' }}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px',
                              borderRadius: 7, cursor: available ? 'pointer' : 'not-allowed',
                              fontSize: 13, opacity: available ? 1 : 0.45,
                              color: 'var(--text-primary)', background: active ? 'var(--hover-bg)' : 'transparent',
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
              <button onClick={() => fileRef.current?.click()} className="yuan-tip" data-tip="上传图片" aria-label="上传图片"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '7px', lineHeight: 1, opacity: 0.7, transition: 'opacity 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: 32, minHeight: 32 }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.7' }}
              ><PaperclipIcon size={17} /></button>
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
              <ModelSelector model={model} onChange={setModel} />
              <ReasoningSelector effort={effort} setEffort={setEffort} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
