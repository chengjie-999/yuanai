import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ChatMessage } from '../../types'
import ToolCallCard from '../ToolCallCard'
import MarkdownContent from '../MarkdownContent'
import { AGENT_CONFIG } from '../../config/agents'
import { voiceTtsStream } from '../../api'
import { LoadingDots, addToken, toSpeechText, splitSpeechSegments, useSecuredUrl } from './helpers'
import { BarChartIcon, BotIcon, ClipboardIcon, PlanetIcon } from '../icons'

// 气泡内图标按钮统一样式（复制/修改/点赞；用户气泡为 accent 底配白色图标）
const iconBtnStyle = (inUserBubble: boolean, active = false): React.CSSProperties => ({
  background: 'none', border: 'none', cursor: 'pointer', padding: '4px', borderRadius: 6,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: inUserBubble ? 'rgba(255,255,255,0.9)' : (active ? 'var(--accent)' : 'var(--text-muted)'),
  opacity: 0.65, transition: 'opacity 0.15s', minWidth: 26, minHeight: 26, lineHeight: 1,
})

const iconProps = { width: 13, height: 13, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

// 全局朗读互斥：同一时刻只允许一个气泡出声，新朗读自动打断旧的
let globalStopReading: (() => void) | null = null

/* 交互图表 iframe：5 秒 sse token + 沙箱（S1.2，不落长期 JWT、不给 allow-same-origin） */
function HtmlFrame({ url, title }: { url: string; title: string }) {
  const src = useSecuredUrl(url)
  return (
    <div style={{
      borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
      background: 'var(--bg-primary)', aspectRatio: '2/1', maxHeight: 450,
    }}>
      <iframe src={src} sandbox="allow-scripts" title={title}
        style={{ width: '100%', height: '100%', border: 'none' }} />
    </div>
  )
}

const MessageBubble = React.memo(function MessageBubbleInner({ msg, index, isLast, loading, liked, disliked, editing, user, setExpandedImage, onEditStart, onEditConfirm, onEditCancel, onFeedback, onRegenerate, autoRead, autoReadTick }: {
  msg: ChatMessage; index: number; isLast: boolean; loading: boolean
  liked?: boolean; disliked?: boolean; editing?: boolean
  user?: any; setExpandedImage: (v: string | null) => void
  onEditStart: (i: number) => void
  onEditConfirm: (i: number, content: string) => void
  onEditCancel: () => void
  onFeedback: (i: number, kind: 'like' | 'dislike') => void
  onRegenerate?: (i: number) => void
  autoRead?: boolean; autoReadTick?: number
}) {
  const isUser = msg.role === 'user'
  const sender = !isUser ? (msg.sender || 'orchestrator') : null
  const agent = sender ? AGENT_CONFIG[sender] : null
  const [copied, setCopied] = useState(false)
  const [draft, setDraft] = useState(msg.content)
  // 朗读状态（AI 气泡）：获取中/播放中
  const [speaking, setSpeaking] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // 下一段预加载的音频（播完当前立即接上，消除分片接缝）
  const preloadRef = useRef<{ el: HTMLAudioElement; url: string } | null>(null)
  // 朗读序号：打断/重新朗读时递增，作废在途的合成请求
  const readSeqRef = useRef(0)
  // 进入编辑态时预填原内容
  useEffect(() => { if (editing) setDraft(msg.content) }, [editing])
  // 自动朗读：AI 回复完成后（autoReadTick 递增）触发一次；仅在最后一条且开启时
  const autoReadFired = useRef(0)
  useEffect(() => {
    if (!autoRead || !autoReadTick || autoReadTick <= autoReadFired.current) return
    if (isLast && !isUser && msg.content.trim()) {
      autoReadFired.current = autoReadTick
      toggleRead()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoReadTick])

  // 统一停止朗读：暂停 + revoke blob URL + 复位（所有路径必须走这里，防泄漏）
  const stopReading = () => {
    const audio = audioRef.current
    if (audio) {
      try { audio.pause() } catch { /* 忽略 */ }
      try { if (audio.src) URL.revokeObjectURL(audio.src) } catch { /* 忽略 */ }
    }
    const pre = preloadRef.current
    if (pre) {
      try { pre.el.pause() } catch { /* 忽略 */ }
      try { URL.revokeObjectURL(pre.url) } catch { /* 忽略 */ }
      preloadRef.current = null
    }
    audioRef.current = null
    setSpeaking(false)
    if (globalStopReading === stopReading) globalStopReading = null
  }
  // 卸载时停止朗读
  useEffect(() => () => stopReading()
    // eslint-disable-next-line react-hooks/exhaustive-deps
    , [])

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

  // 朗读消息（豆包 TTS 分段连播）：口语化文本 → 按句分段（≤200 字/段）→
  // 串行合成 + 预取 1 段 → 每段一个 Audio 整段播放（段内不再字节切分，
  // 根除接缝咔哒；帧协议保证整帧边界）。长文不再截断（原 slice(0,1000)
  // 静默丢尾）。再点一次打断（作废在途请求）
  const toggleRead = async () => {
    if (speaking) {
      readSeqRef.current += 1  // 作废在途合成请求
      stopReading()
      return
    }
    const seq = ++readSeqRef.current
    // 全局互斥：打断其它气泡正在播放的朗读
    if (globalStopReading) globalStopReading()
    globalStopReading = stopReading
    setSpeaking(true)
    try {
      const speech = toSpeechText(msg.content)
      const segments = splitSpeechSegments(speech)
      if (!segments.length) throw new Error('没有可朗读的内容')

      // 段级队列：每段完整合成后才入队（天然抖动缓冲，不饿死）
      const queue: { blob: Blob; isLast: boolean }[] = []
      let playing = false
      let fetchingIdx = 0          // 下一个要发起的合成段
      let activeFetches = 0        // 在途合成数（预取 1 段 → ≤2）
      let allFetched = false
      let fetchError: string | null = null

      const pump = () => {
        if (seq !== readSeqRef.current) return  // 已打断：队列作废
        if (playing) return
        if (!queue.length) {
          if (allFetched) stopReading()  // 全部段播完：正常收尾
          return
        }
        const { blob } = queue.shift()!
        playing = true
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => { URL.revokeObjectURL(url); playing = false; pump() }
        audio.onerror = () => { URL.revokeObjectURL(url); playing = false; pump() }
        const p = audio.play()
        if (p && p.catch) p.catch(() => { playing = false; pump() })
      }

      // 串行预取：发起下一段合成时保持 1 段预取余量（播放第 i 段时第 i+1 段已在途）
      const fetchNext = () => {
        if (seq !== readSeqRef.current || fetchError) return
        if (fetchingIdx >= segments.length) { allFetched = true; pump(); return }
        if (activeFetches >= 2) return  // 在途 ≤2：当前播放段 + 预取段
        const i = fetchingIdx++
        activeFetches += 1
        let settled = false
        const done = () => { if (settled) return; settled = true; activeFetches -= 1 }
        voiceTtsStream(
          segments[i],
          sender || undefined,
          (blob) => {
            if (seq !== readSeqRef.current) return
            queue.push({ blob, isLast: i === segments.length - 1 })
            pump()
            fetchNext()  // 首个分片到达即可预取下一段
          },
          () => { done(); fetchNext() },
        ).catch((err: any) => {
          done()
          if (seq !== readSeqRef.current) return
          fetchError = err?.message || '语音合成失败，请稍后重试'
          allFetched = true
          pump()
        })
      }
      fetchNext()
      // 等待全部完成（fetchError 或正常收尾）——由 pump 的 stopReading 或异常分支收口
      await new Promise<void>((resolve) => {
        const timer = setInterval(() => {
          if (seq !== readSeqRef.current) { clearInterval(timer); resolve(); return }
          if (fetchError) { clearInterval(timer); resolve(); return }
          if (allFetched && !queue.length && !playing) { clearInterval(timer); resolve(); return }
        }, 150)
      })
      if (seq === readSeqRef.current && fetchError) {
        stopReading()
        alert(fetchError)
      }
    } catch (err: any) {
      if (seq === readSeqRef.current) {
        stopReading()
        alert(err?.message || '语音合成失败，请稍后重试')
      }
    }
  }

  // 编辑态用保存/取消替换操作行；空内容的占位/工具气泡不显示操作行
  const showActions = !editing && msg.content.trim().length > 0

  // 气泡内操作行（常显，按钮本体 0.65 → 1 hover 微反馈）
  const bubbleActions = showActions ? (
    <div className="msg-actions" style={{ display: 'flex', gap: 2, justifyContent: 'flex-end', marginTop: 6, marginBottom: -4 }}>
      {!isUser && (
        <button onClick={toggleRead} className="yuan-tip" data-tip={speaking ? '打断朗读' : '朗读'} aria-label={speaking ? '打断朗读' : '朗读'}
          style={iconBtnStyle(false, speaking)}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          {speaking ? (
            // 朗读中：跳动波形动画，点击打断
            <span className="msg-read-bars" style={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, height: 13 }}>
              <i style={{ width: 2, height: 5, background: 'var(--accent)', borderRadius: 1, animation: 'msgReadBar 0.9s ease-in-out infinite' }} />
              <i style={{ width: 2, height: 11, background: 'var(--accent)', borderRadius: 1, animation: 'msgReadBar 0.9s ease-in-out 0.15s infinite' }} />
              <i style={{ width: 2, height: 8, background: 'var(--accent)', borderRadius: 1, animation: 'msgReadBar 0.9s ease-in-out 0.3s infinite' }} />
              <i style={{ width: 2, height: 12, background: 'var(--accent)', borderRadius: 1, animation: 'msgReadBar 0.9s ease-in-out 0.45s infinite' }} />
            </span>
          ) : (
            <svg {...iconProps}>
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            </svg>
          )}
        </button>
      )}
      <button onClick={copyContent} className="yuan-tip" data-tip="复制" aria-label="复制"
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
        <button onClick={() => onEditStart(index)} disabled={loading} className="yuan-tip" data-tip="修改" aria-label="修改"
          style={iconBtnStyle(isUser)}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          <svg {...iconProps}><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /></svg>
        </button>
      ) : (
        <>
        <button onClick={() => onFeedback(index, 'like')} disabled={loading}
          className="yuan-tip" data-tip={liked ? '取消点赞' : '点赞'} aria-label={liked ? '取消点赞' : '点赞'}
          style={iconBtnStyle(false, !!liked)}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          <svg {...iconProps} fill={liked ? 'currentColor' : 'none'}>
            <path d="M7 10v12" />
            <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z" />
          </svg>
        </button>
        <button onClick={() => onFeedback(index, 'dislike')} disabled={loading}
          className="yuan-tip" data-tip={disliked ? '取消点踩' : '点踩（内容不会进入记忆）'} aria-label={disliked ? '取消点踩' : '点踩'}
          style={{ ...iconBtnStyle(false, !!disliked), color: disliked ? 'var(--danger)' : undefined }}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
          <svg {...iconProps} fill={disliked ? 'currentColor' : 'none'}>
            <path d="M17 14V2" />
            <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
          </svg>
        </button>
        {/* 重新生成：截断本条及其后消息，重发它前面的最后一条用户消息（豆包式） */}
        {onRegenerate && (
          <button onClick={() => onRegenerate(index)} disabled={loading}
            className="yuan-tip" data-tip="重新生成" aria-label="重新生成"
            style={iconBtnStyle(false)}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
            <svg {...iconProps}><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></svg>
          </button>
        )}
        </>
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
                  <button onClick={onEditCancel} className="yuan-tip" data-tip="取消" aria-label="取消"
                    style={{ ...iconBtnStyle(true), opacity: 0.9, background: 'rgba(255,255,255,0.15)' }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '0.9'}>
                    <svg {...iconProps}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                  </button>
                  <button onClick={() => onEditConfirm(index, draft)} disabled={!draft.trim()}
                    className="yuan-tip" data-tip="保存" aria-label="保存"
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
              <Link to={msg.pageLink}
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 6, padding: '5px 12px',
                  borderRadius: 6, background: agent?.color || 'var(--accent)',
                  color: '#fff', fontSize: 12, fontWeight: 500, textDecoration: 'none',
                  transition: 'opacity 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >{msg.sender === 'analysis' ? <BarChartIcon size={13} /> : msg.sender === 'automation' ? <BotIcon size={13} /> : msg.sender === 'planet' ? <PlanetIcon size={13} /> : <ClipboardIcon size={13} />} 打开面板</Link>
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
                  <HtmlFrame key={j} url={url} title={`交互图表 ${j + 1}`} />
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
)

export default MessageBubble
