import type { ChatMessage } from '../../types'
import ToolCallCard from '../ToolCallCard'
import MarkdownContent from '../MarkdownContent'
import { AGENT_CONFIG } from '../../config/agents'
import { LoadingDots, addToken } from './helpers'

export default function MessageBubble({ msg, isLast, loading, user, setExpandedImage }: {
  msg: ChatMessage; isLast: boolean; loading: boolean
  user?: any; setExpandedImage: (v: string | null) => void
}) {
  const isUser = msg.role === 'user'
  const sender = !isUser ? (msg.sender || 'orchestrator') : null
  const agent = sender ? AGENT_CONFIG[sender] : null

  return (
    <div style={{
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
        background: isUser ? '#1976d2' : 'var(--bg-tertiary)',
        color: isUser ? '#fff' : 'var(--text-primary)',
        borderLeft: agent ? `3px solid ${agent.color}` : undefined,
        boxShadow: isUser
          ? '0 1px 3px rgba(25,118,210,0.15)'
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
            {msg.content}
            {msg.images && msg.images.length > 0 && (
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginTop: 8 }}>
                {msg.images.map((img, j) => (
                  <img key={j} src={addToken(img)}
                    onClick={() => setExpandedImage(addToken(img))}
                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid #e0e0e0' }} />
                ))}
              </div>
            )}
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
            {msg.reasoning && (
              <details open={loading && isLast && !msg.content} style={{ marginBottom: 8 }}>
                <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none', outline: 'none' }}>
                  {loading && isLast && !msg.content ? '思考中...' : `思考完成${msg.reasoningTime ? ` (${msg.reasoningTime}s)` : ''}`}
                </summary>
                <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                  {msg.reasoning}
                </div>
              </details>
            )}
            <MarkdownContent content={msg.content} />
            {msg.pageLink && (
              <a href={msg.pageLink} target="_blank" rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'inline-block', marginTop: 6, padding: '5px 12px',
                  borderRadius: 6, background: agent?.color || '#1976d2',
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
                  <img key={j} src={addToken(img)}
                    onClick={() => setExpandedImage(addToken(img))}
                    style={{ height: 120, borderRadius: 6, flexShrink: 0, cursor: 'pointer', border: '1px solid #e0e0e0' }} />
                ))}
              </div>
            )}
          </>
        )}
        {msg.toolCalls?.map((tc, j) => (
          <ToolCallCard key={j} call={tc} />
        ))}
      </div>
    </div>
  )
}
