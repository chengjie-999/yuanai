import { useEffect, useState } from 'react'
import type { ChatMessage } from '../../types'
import ToolCallCard from '../ToolCallCard'
import MarkdownContent from '../MarkdownContent'
import { AGENT_CONFIG } from '../../config/agents'
import { LoadingDots, addToken } from './helpers'

// 气泡内图标按钮统一样式（复制/修改/点赞；用户气泡为 accent 底配白色图标）
const iconBtnStyle = (inUserBubble: boolean, active = false): React.CSSProperties => ({
  background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: 6,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: inUserBubble ? 'rgba(255,255,255,0.9)' : (active ? 'var(--accent)' : 'var(--text-muted)'),
  opacity: 0.65, transition: 'opacity 0.15s', minWidth: 26, minHeight: 26, lineHeight: 1,
})

const iconProps = { width: 13, height: 13, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

export default function MessageBubble({ msg, index, isLast, loading, liked, editing, user, setExpandedImage, onEditStart, onEditConfirm, onEditCancel, onLike }: {
  msg: ChatMessage; index: number; isLast: boolean; loading: boolean
  liked?: boolean; editing?: boolean
  user?: any; setExpandedImage: (v: string | null) => void
  onEditStart: (i: number) => void
  onEditConfirm: (i: number, content: string) => void
  onEditCancel: () => void
  onLike: (i: number) => void
}) {
  const isUser = msg.role === 'user'
  const sender = !isUser ? (msg.sender || 'orchestrator') : null
  const agent = sender ? AGENT_CONFIG[sender] : null
  const [copied, setCopied] = useState(false)
  const [draft, setDraft] = useState(msg.content)
  // 进入编辑态时预填原内容
  useEffect(() => { if (editing) setDraft(msg.content) }, [editing])

  const copyContent = async () => {
    // 复制 msg.content 原样（AI 消息即 markdown 原文）
    try { await navigator.clipboard.writeText(msg.content) }
    catch {
      const ta = document.createElement('textarea')
      ta.value = msg.content
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  // 编辑态用保存/取消替换操作行；空内容的占位/工具气泡不显示操作行
  const showActions = !editing && msg.content.trim().length > 0

  // 气泡内操作行（常显，按钮本体 0.65 → 1 hover 微反馈）
  const bubbleActions = showActions ? (
    <div className="msg-actions" style={{ display: 'flex', gap: 2, justifyContent: 'flex-end', marginTop: 6, marginBottom: -4 }}>
      <button onClick={copyContent} title="复制" aria-label="复制"
        style={iconBtnStyle(isUser, copied)}
        onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
        onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
        {copied ? (
          <svg {...iconProps}><polyline points="20 6 9 17 4 12" /></svg>
        ) : (
          <svg {...iconProps}>
            <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
            <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
          </svg>
        )}
      </button>
      {isUser ? (
        <button onClick={() => onEditStart(index)} disabled={loading} title="修改" aria-label="修改"
          style={iconBtnStyle(isUser)}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          <svg {...iconProps}><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /></svg>
        </button>
      ) : (
        <button onClick={() => onLike(index)} disabled={loading}
          title={liked ? '取消点赞' : '点赞'} aria-label={liked ? '取消点赞' : '点赞'}
          style={iconBtnStyle(false, !!liked)}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          <svg {...iconProps} fill={liked ? 'currentColor' : 'none'}>
            <path d="M7 10v12" />
            <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z" />
          </svg>
        </button>
      )}
    </div>
  ) : null

  return (
    <div className="chat-msg-row" style={{
      marginBottom: 14,
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
    }}>
      {agent && (
        <div style={{
          fontSize: 12, fontWeight: 600, marginBottom: 3, marginLeft: 2,
          color: agent.color, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: agent.color,
            display: 'inline-block', flexShrink: 0,
          }} />
          {agent.label}
        </div>
      )}
      {isUser && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3, marginRight: 4, fontWeight: 500 }}>
          {user?.display_name || user?.username || '我'}
        </div>
      )}

      <div className="chat-msg-bubble" style={{
        padding: '10px 16px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '4px 14px 14px 14px',
        maxWidth: '75%',
        background: isUser ? 'var(--accent)' : 'var(--bg-tertiary)',
        color: isUser ? '#fff' : 'var(--text-primary)',
        borderLeft: agent ? `3px solid ${agent.color}` : undefined,
        boxShadow: isUser
          ? '0 1px 3px rgba(88,157,246,0.2)'
          : '0 1px 2px var(--shadow-sm)',
        whiteSpace: 'pre-wrap',
        fontSize: 14,
        lineHeight: 1.65,
        overflowWrap: 'break-word',
        wordBreak: 'break-word',
      }}>
        {loading && isLast && msg.role === 'assistant' && !msg.content && (!msg.toolCalls || msg.toolCalls.length === 0) ? (
          <LoadingDots />
        ) : isUser ? (
          <>
            {editing ? (
              <div style={{ minWidth: 220 }}>
                <textarea className="msg-edit-textarea" value={draft} autoFocus rows={3}
                  onChange={(e) => setDraft(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg-primary)',
                    color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: 8,
                    fontSize: 14, padding: '8px 10px', fontFamily: 'inherit', resize: 'vertical',
                    display: 'block', outline: 'none' }} />
                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', marginTop: 8 }}>
                  <button onClick={onEditCancel} title="取消" aria-label="取消"
                    style={{ ...iconBtnStyle(true), opacity: 0.9, background: 'rgba(255,255,255,0.15)' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '0.9'}>
                    <svg {...iconProps}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                  </button>
                  <button onClick={() => onEditConfirm(index, draft)} disabled={!draft.trim()}
                    title="保存" aria-label="保存"
                    style={{ ...iconBtnStyle(true), background: '#fff', color: 'var(--accent)', opacity: draft.trim() ? 0.95 : 0.5 }}>
                    <svg {...iconProps}><polyline points="20 6 9 17 4 12" /></svg>
                  </button>
                </div>
              </div>
            ) : (
              <>{msg.content}</>
            )}
            {msg.images && msg.images.length > 0 && (
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginTop: 8 }}>
                {msg.images.map((img, j) => (
                  <img key={j} src={addToken(img)} loading="lazy"
                    onClick={() => setExpandedImage(addToken(img))}
                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid var(--border)' }} />
                ))}
              </div>
            )}
            {bubbleActions}
          </>
        ) : (
          <>
            {msg.progress && (
              <div style={{ marginBottom: 8, padding: '6px 10px', background: 'var(--accent-light)', borderRadius: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  <span>{msg.progress.message || '处理中...'}</span>
                  <span>{msg.progress.current}/{msg.progress.total}</span>
                </div>
                <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.round((msg.progress.current / Math.max(msg.progress.total, 1)) * 100)}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s' }} />
                </div>
              </div>
            )}
            {(msg.reasoning || msg.toolCalls?.length) ? (
              <details open={loading && isLast && !msg.content} style={{ marginBottom: 8 }}>
                <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none', outline: 'none' }}>
                  {loading && isLast && !msg.content ? '执行中...' : msg.reasoning ? `思考与工具调用${msg.reasoningTime ? ` (${msg.reasoningTime}s)` : ''}` : `工具调用 (${msg.toolCalls!.length} 项)`}
                </summary>
                {msg.reasoning && (
                  <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                    {msg.reasoning}
                  </div>
                )}
                {msg.toolCalls?.map((tc, j) => (
                  <ToolCallCard key={j} call={tc} />
                ))}
              </details>
            ) : null}
            <MarkdownContent content={msg.content} />
            {msg.pageLink && (
              <a href={msg.pageLink} target="_blank" rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'inline-block', marginTop: 6, padding: '5px 12px',
                  borderRadius: 6, background: agent?.color || 'var(--accent)',
                  color: '#fff', fontSize: 12, fontWeight: 500, textDecoration: 'none',
                  transition: 'opacity 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >{msg.sender === 'analysis' ? '📊' : msg.sender === 'automation' ? '🤖' : '📋'} 打开面板 →</a>
            )}
            {msg.images && msg.images.length > 0 && (
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginTop: 8 }}>
                {msg.images.map((img, j) => (
                  <img key={j} src={addToken(img)} loading="lazy"
                    onClick={() => setExpandedImage(addToken(img))}
                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid var(--border)' }} />
                ))}
              </div>
            )}
            {msg.htmls && msg.htmls.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                {msg.htmls.map((url, j) => (
                  <div key={j} style={{
                    borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
                    background: 'var(--bg-primary)', aspectRatio: '2/1', maxHeight: 450,
                  }}>
                    <iframe src={addToken(url)} style={{
                      width: '100%', height: '100%', border: 'none',
                    }} title={`交互图表 ${j + 1}`} />
                  </div>
                ))}
              </div>
            )}
            {bubbleActions}
          </>
        )}
      </div>
    </div>
  )
}
