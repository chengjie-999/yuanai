import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ChatMessage } from '../../types'
import ToolCallCard from '../ToolCallCard'
import TerminalView, { isTerminalCall } from './TerminalView'
import MarkdownContent from '../MarkdownContent'
import { AGENT_CONFIG } from '../../config/agents'
import { useTheme } from '../../contexts/ThemeContext'
import { voiceTtsStream } from '../../api'
import { LoadingDots, addToken, toSpeechText, splitSpeechSegments, useSecuredUrl, splitSpecialBlocks } from './helpers'
import { BarChartIcon, BotIcon, ClipboardIcon, PlanetIcon, LinkIcon, CheckIcon, CopyIcon, XIcon } from '../icons'
import ZoomableImage from './ZoomableImage'

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
    <div className="chat-html-frame" style={{
      borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
      background: 'var(--bg-primary)', aspectRatio: '2/1', maxHeight: 450,
    }}>
      <iframe src={src} sandbox="allow-scripts" title={title}
        style={{ width: '100%', height: '100%', border: 'none' }} />
    </div>
  )
}

/* 模型输出 HTML 直渲（2026-10-26）：srcDoc + 沙箱 iframe——脚本允许（图表可交互）
   但 opaque origin 无法触碰页面数据（不给 allow-same-origin，同 HtmlFrame 口径） */
function InlineHtmlFrame({ html }: { html: string }) {
  const [showSource, setShowSource] = useState(false)
  const [copied, setCopied] = useState(false)
  const [zoom, setZoom] = useState(false)
  const { isDark } = useTheme()
  const isDoc = /^\s*<!DOCTYPE html/i.test(html) || /^\s*<html[\s>]/i.test(html)
  // 主题适配（2026-10-26）：完整文档注入 color-scheme（尊重文档自带配色）；
  // 片段外壳按站点明暗显式上色（iframe 不继承站点的 data-theme）
  const srcDoc = isDoc
    ? html.replace(/(<head[^>]*>)/i, `$1<meta name="color-scheme" content="light dark">`)
    : (
      `<!DOCTYPE html><html><head><meta charset="utf-8">`
      + `<style>body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:16px;line-height:1.7;`
      + (isDark
        ? `background:#0b1220;color:#e2e8f0}table{border-collapse:collapse}td,th{border:1px solid #2b3b56;padding:6px 10px}`
        : `color:#1f2937}table{border-collapse:collapse}td,th{border:1px solid #d1d5db;padding:6px 10px}`)
      + `a{color:#60a5fa}</style></head><body>${html}</body></html>`
    )
  const copy = () => {
    navigator.clipboard?.writeText(html).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div style={{
      margin: '8px 0', borderRadius: 10, overflow: 'hidden',
      border: '1px solid var(--border)', background: 'var(--bg-primary)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
        background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-light)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>HTML 渲染</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => setZoom(true)} className="yuan-tip" data-tip="全屏查看"
          aria-label="全屏查看"
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                   color: 'var(--accent)', padding: '2px 4px' }}>
          放大
        </button>
        <button onClick={() => setShowSource((s) => !s)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
            color: 'var(--text-muted)', padding: '2px 4px',
          }}>
          {showSource ? '隐藏源码' : '查看源码'}
        </button>
        <button onClick={copy} className="yuan-tip" data-tip={copied ? '已复制' : '复制源码'}
          aria-label="复制源码"
          style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 2,
            color: copied ? 'var(--success)' : 'var(--text-muted)', display: 'flex',
          }}>
          {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
        </button>
      </div>
      {showSource && (
        <pre style={{
          margin: 0, padding: '8px 10px', fontSize: 11, maxHeight: 160, overflow: 'auto',
          borderBottom: '1px solid var(--border-light)', background: 'var(--bg-tertiary)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        }}>{html}</pre>
      )}
      <iframe srcDoc={srcDoc} sandbox="allow-scripts" title="HTML 渲染"
        style={{ width: '100%', height: 420, border: 'none', display: 'block' }} />
      {zoom && <HtmlViewer html={srcDoc} onClose={() => setZoom(false)} />}
    </div>
  )
}

/* 全屏查看器（2026-10-29）：HTML 渲染结果像图片一样放大查看——
   沙箱 iframe 保持 allow-scripts 隔离，不给越界新标签（blob 同源脚本 XSS 风险） */
function HtmlViewer({ html, onClose }: { html: string; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 'min(1200px, 96vw)', height: 'min(90vh, 900px)', display: 'flex',
        flexDirection: 'column', background: 'var(--bg-primary)', borderRadius: 12,
        overflow: 'hidden', boxShadow: '0 12px 48px rgba(0,0,0,0.4)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 14px', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-secondary)',
        }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>HTML 全屏查看</span>
          <button onClick={onClose} aria-label="关闭"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                     color: 'var(--text-muted)', display: 'flex', lineHeight: 1 }}>
            <XIcon size={16} />
          </button>
        </div>
        <iframe srcDoc={html} sandbox="allow-scripts" title="HTML 全屏查看"
          style={{ flex: 1, width: '100%', border: 'none' }} />
      </div>
    </div>
  )
}

/* Mermaid 图表直渲（2026-10-26）：动态 import 按需加载，不进主包；
   主题跟随明暗切换重渲染；语法错误回退显示源码；可像图片一样放大（2026-10-29） */
function MermaidBlock({ code }: { code: string }) {
  const [svg, setSvg] = useState('')
  const [err, setErr] = useState('')
  const [showSource, setShowSource] = useState(false)
  const [copied, setCopied] = useState(false)
  const [zoom, setZoom] = useState(false)
  const { isDark } = useTheme()
  useEffect(() => {
    let alive = true
    let disposed = false
    import('mermaid').then((mod) => {
      const m = mod.default
      m.initialize({ startOnLoad: false, theme: isDark ? 'dark' : 'default',
                     fontFamily: '-apple-system, PingFang SC, Microsoft YaHei, sans-serif' })
      m.render(`mmd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, code)
        .then((r: { svg: string }) => { if (alive && !disposed) { setSvg(r.svg); setErr('') } })
        .catch((e: unknown) => { if (alive && !disposed) setErr(String(e)) })
        .finally(() => { disposed = true })
    }).catch(() => { if (alive) setErr('mermaid 加载失败（网络受限？）') })
    return () => { alive = false }
  }, [code, isDark])
  const copy = () => {
    navigator.clipboard?.writeText(code).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div style={{
      margin: '8px 0', borderRadius: 10, overflow: 'hidden',
      border: '1px solid var(--border)', background: 'var(--bg-primary)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
        background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-light)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>图表</span>
        <div style={{ flex: 1 }} />
        {svg && (
          <button onClick={() => setZoom(true)} className="yuan-tip" data-tip="放大查看"
            aria-label="放大查看"
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                     color: 'var(--accent)', padding: '2px 4px' }}>
            放大
          </button>
        )}
        <button onClick={() => setShowSource((s) => !s)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                   color: 'var(--text-muted)', padding: '2px 4px' }}>
          {showSource ? '隐藏源码' : '查看源码'}
        </button>
        <button onClick={copy} className="yuan-tip" data-tip={copied ? '已复制' : '复制源码'}
          aria-label="复制源码"
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                   color: copied ? 'var(--success)' : 'var(--text-muted)', display: 'flex' }}>
          {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
        </button>
      </div>
      {showSource && (
        <pre style={{
          margin: 0, padding: '8px 10px', fontSize: 11, maxHeight: 160, overflow: 'auto',
          borderBottom: '1px solid var(--border-light)', background: 'var(--bg-tertiary)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        }}>{code}</pre>
      )}
      {svg ? (
        <div style={{ padding: 12, overflow: 'auto', display: 'flex', justifyContent: 'center' }}
          dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <div style={{ padding: '16px 12px', fontSize: 12, color: err ? 'var(--danger)' : 'var(--text-muted)' }}>
          {err ? `图表语法错误：${err}` : '图表渲染中…'}
        </div>
      )}
      {zoom && svg && (
        <ZoomableImage
          src={`data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`}
          onClose={() => setZoom(false)} />
      )}
    </div>
  )
}

/* SVG 直渲（2026-10-26）：img + data URI——img 上下文不执行脚本，天然安全 */
function SvgBlock({ code }: { code: string }) {
  const [showSource, setShowSource] = useState(false)
  const [copied, setCopied] = useState(false)
  const [zoom, setZoom] = useState(false)
  const uri = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(code)))}`
  const copy = () => {
    navigator.clipboard?.writeText(code).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div style={{
      margin: '8px 0', borderRadius: 10, overflow: 'hidden',
      border: '1px solid var(--border)', background: 'var(--bg-primary)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '5px 10px',
        background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-light)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>SVG 图形</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowSource((s) => !s)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11,
                   color: 'var(--text-muted)', padding: '2px 4px' }}>
          {showSource ? '隐藏源码' : '查看源码'}
        </button>
        <button onClick={copy} className="yuan-tip" data-tip={copied ? '已复制' : '复制源码'}
          aria-label="复制源码"
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                   color: copied ? 'var(--success)' : 'var(--text-muted)', display: 'flex' }}>
          {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
        </button>
      </div>
      {showSource && (
        <pre style={{
          margin: 0, padding: '8px 10px', fontSize: 11, maxHeight: 160, overflow: 'auto',
          borderBottom: '1px solid var(--border-light)', background: 'var(--bg-tertiary)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        }}>{code}</pre>
      )}
      <div style={{ padding: 12, display: 'flex', justifyContent: 'center', overflow: 'auto' }}>
        <img src={uri} alt="SVG 图形" style={{ maxWidth: '100%', cursor: 'zoom-in' }}
          onClick={() => setZoom(true)} title="点击放大" />
      </div>
      {zoom && <ZoomableImage src={uri} onClose={() => setZoom(false)} />}
    </div>
  )
}

const MessageBubble = React.memo(function MessageBubbleInner({ msg, index, isLast, loading, liked, disliked, editing, user, setExpandedImage, onEditStart, onEditConfirm, onEditCancel, onFeedback, onReport, onRegenerate, onContinue, autoRead, autoReadTick, onOpenPanel }: {
  msg: ChatMessage; index: number; isLast: boolean; loading: boolean
  liked?: boolean; disliked?: boolean; editing?: boolean
  user?: any; setExpandedImage: (v: string | null) => void
  onEditStart: (i: number) => void
  onEditConfirm: (i: number, content: string) => void
  onEditCancel: () => void
  onFeedback: (i: number, kind: 'like' | 'dislike') => void
  onReport?: (i: number) => void
  onRegenerate?: (i: number) => void
  onContinue?: () => void
  autoRead?: boolean; autoReadTick?: number
  onOpenPanel?: (link: string) => void
}) {
  const isUser = msg.role === 'user'
  const sender = !isUser ? (msg.sender || 'orchestrator') : null
  const agent = sender ? AGENT_CONFIG[sender] : null
  const [copied, setCopied] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)
  const [draft, setDraft] = useState(msg.content)
  // P1-3 思考块受控展开：流式期间保持展开（随 reasoning 增长可见），
  // 完成后默认收起；用户手动折叠/展开后尊重其选择（不被后续 token 重置）
  const [thinkOpen, setThinkOpen] = useState(false)
  const userToggledRef = useRef(false)
  useEffect(() => {
    if (loading && isLast && !userToggledRef.current) setThinkOpen(true)
    else if (!loading && !userToggledRef.current) setThinkOpen(false)
  }, [loading, isLast, msg.reasoning?.length, msg.finalReasoning?.length, msg.toolCalls?.length])
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
      toggleRead(true)  // 自动朗读：失败静默不弹窗
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
    // C5 AI 标识（2026-10-29）：复制内容附显式标识（《标识办法》第 4 条
    // 下载/复制/导出须含标识）——用户消息原样，AI 消息追加声明
    const text = isUser ? msg.content : `${msg.content}

（以上内容由 AI 生成）`
    try { await navigator.clipboard.writeText(text) }
    catch {
      const ta = document.createElement('textarea')
      ta.value = text
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
  // 根除接缝咔哒；帧协议保证整帧边界）。长文不再截断。再点一次打断。
  // P1-6：单段合成失败跳过继续下一段（不再整体停）；自动朗读失败静默
  const toggleRead = async (isAuto = false) => {
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
    // C5 音频标识（2026-10-29）：朗读开始前播双音提示音（《标识办法》对合成音频的
    // 提示音要求；Web Audio 合成零依赖；整条消息一次，分段连播不重复；失败静默）
    try {
      const AC = window.AudioContext || (window as any).webkitAudioContext
      if (AC) {
        const ctx = new AC()
        if (ctx.state === 'suspended') ctx.resume().catch(() => {})
        const t0 = ctx.currentTime + 0.02
        const note = (freq: number, start: number, dur: number) => {
          const o = ctx.createOscillator()
          const g = ctx.createGain()
          o.type = 'sine'
          o.frequency.value = freq
          g.gain.setValueAtTime(0.0001, t0 + start)
          g.gain.exponentialRampToValueAtTime(0.12, t0 + start + 0.02)
          g.gain.exponentialRampToValueAtTime(0.0001, t0 + start + dur)
          o.connect(g)
          g.connect(ctx.destination)
          o.start(t0 + start)
          o.stop(t0 + start + dur + 0.05)
        }
        note(880, 0, 0.12)
        note(1174.66, 0.14, 0.16)
        setTimeout(() => { ctx.close().catch(() => {}) }, 600)
      }
    } catch { /* 提示音失败不影响朗读 */ }
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
      let failedSegments = 0       // 合成失败段数（全失败才提示；部分失败跳过继续）

      const pump = () => {
        if (seq !== readSeqRef.current) return  // 已打断：队列作废
        if (playing) return
        if (!queue.length) {
          if (allFetched) stopReading()  // 全部段处理完：正常收尾
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
        if (seq !== readSeqRef.current) return
        if (fetchingIdx >= segments.length) { allFetched = true; pump(); return }
        if (activeFetches >= 2) return  // 在途 ≤2：当前播放段 + 预取段
        const i = fetchingIdx++
        activeFetches += 1
        let settled = false
        const done = () => { if (settled) return; settled = true; activeFetches -= 1 }
        // 2026-10-19 修复：onFragment 按 8KB 音频帧回调——此前每帧单独入队、
        // 每帧一个 Audio 播放（与「每段一个 Audio 整段播放」设计不符，帧边界
        // 接缝咔哒）；改为帧聚合，段完成（onDone）时整段入队
        const segBuf: Blob[] = []
        voiceTtsStream(
          segments[i],
          sender || undefined,
          (blob) => { if (seq === readSeqRef.current) segBuf.push(blob) },
          () => {
            done()
            if (seq === readSeqRef.current && segBuf.length) {
              queue.push({ blob: new Blob(segBuf, { type: 'audio/mpeg' }), isLast: i === segments.length - 1 })
              pump()
            }
            fetchNext()  // 首段完成即可预取下一段
          },
        ).catch(() => {
          done()
          failedSegments += 1
          // P1-6：单段失败跳过继续下一段（此前 fetchError → 整体停播，导致「只读一小段」）
          fetchNext()
        })
      }
      fetchNext()
      // 等待全部完成（全部段处理完或 seq 作废）
      await new Promise<void>((resolve) => {
        const timer = setInterval(() => {
          if (seq !== readSeqRef.current) { clearInterval(timer); resolve(); return }
          if (allFetched && !queue.length && !playing && activeFetches === 0) { clearInterval(timer); resolve(); return }
        }, 150)
      })
      // 全部段都失败才提示；自动朗读失败静默（P1-6）
      if (seq === readSeqRef.current && failedSegments >= segments.length && !isAuto) {
        stopReading()
        alert('语音合成失败，请稍后重试')
      }
    } catch (err: any) {
      if (seq === readSeqRef.current) {
        stopReading()
        if (!isAuto) alert(err?.message || '语音合成失败，请稍后重试')
      }
    }
  }

  // 编辑态用保存/取消替换操作行；空内容的占位/工具气泡不显示操作行
  const showActions = !editing && msg.content.trim().length > 0

  // 气泡内操作行（常显，按钮本体 0.65 → 1 hover 微反馈）
  const bubbleActions = showActions ? (
    <div className="msg-actions" style={{ display: 'flex', gap: 2, justifyContent: 'flex-end', marginTop: 6, marginBottom: -4 }}>
      {!isUser && (
        <button onClick={() => toggleRead()} className="yuan-tip" data-tip={speaking ? '打断朗读' : '朗读'} aria-label={speaking ? '打断朗读' : '朗读'}
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
        {/* 举报（C7 投诉举报机制，2026-10-29）：落工单由管理员处理 */}
        {onReport && (
          <button onClick={() => onReport(index)} disabled={loading}
            className="yuan-tip" data-tip="举报" aria-label="举报"
            style={iconBtnStyle(false)}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
            <svg {...iconProps}>
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
              <line x1="4" x2="4" y1="22" y2="15" />
            </svg>
          </button>
        )}
        {/* 重新生成：只替换本条气泡（2026-10-25 起不再截断其后消息） */}
        {onRegenerate && (
          <button onClick={() => onRegenerate(index)} disabled={loading}
            className="yuan-tip" data-tip="重新生成" aria-label="重新生成"
            style={iconBtnStyle(false)}
            onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
            onMouseLeave={(e) => e.currentTarget.style.opacity = '0.65'}>
            <svg {...iconProps}><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></svg>
          </button>
        )}
        {/* U4 继续生成：回答被 max_tokens 截断（后端 finish_reason=length 标志） */}
        {msg.truncated && onContinue && (
          <button onClick={onContinue} disabled={loading}
            className="yuan-tip" data-tip="让 AI 接着写完整" aria-label="继续生成"
            style={{
              marginLeft: 6, padding: '3px 12px', borderRadius: 999,
              border: '1px solid var(--accent)', background: 'var(--accent-light)',
              color: 'var(--accent)', fontSize: 12, fontWeight: 600,
              cursor: loading ? 'default' : 'pointer', lineHeight: 1.6,
            }}>
            继续生成
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
      maxWidth: '100%',
      minWidth: 0,  // 溢出修复：防止行内 flex 链把整页撑出横向滚动
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
          {/* C5 AI 标识（2026-10-29，《标识办法》第 4 条）：AI 气泡常显徽标 */}
          <span style={{
            fontSize: 10, fontWeight: 500, padding: '1px 6px', borderRadius: 999,
            background: 'var(--bg-tertiary)', color: 'var(--text-muted)',
            flexShrink: 0, lineHeight: 1.5,
          }}>AI 生成</span>
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
        minWidth: 0,  // 2026-10-26 溢出修复：flex 项默认 min-width:auto 会被
                      // 超长内容撑开——min-width:0 让气泡严守 75% 上限
        background: isUser ? 'var(--accent)' : 'var(--bg-tertiary)',
        color: isUser ? '#fff' : 'var(--text-primary)',
        borderLeft: agent ? `3px solid ${agent.color}` : undefined,
        boxShadow: isUser
          ? '0 1px 3px rgba(88,157,246,0.2)'
          : '0 1px 2px var(--shadow-sm)',
        whiteSpace: 'pre-wrap',
        fontSize: 14,
        lineHeight: 1.65,
        overflowWrap: 'anywhere',  // 超长无空格串（长链接/base64/长 token）硬折行
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
            {(msg.reasoning || msg.finalReasoning || msg.toolCalls?.length) ? (
              <details open={thinkOpen} style={{ marginBottom: 8 }}
                onToggle={(e) => { userToggledRef.current = true; setThinkOpen((e.target as HTMLDetailsElement).open) }}>
                <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none', outline: 'none' }}>
                  {loading && isLast && !msg.content ? '执行中...'
                    : msg.toolCalls?.length
                      ? `${(msg.reasoning || msg.finalReasoning) ? `思考${msg.reasoningTime ? ` (${msg.reasoningTime}s)` : ''} · ` : ''}${msg.toolCalls.length} 次工具调用`
                      : `思考过程${msg.reasoningTime ? ` (${msg.reasoningTime}s)` : ''}`}
                </summary>
                {/* 旧消息：整段思考（时序交叉改造前的历史数据） */}
                {msg.reasoning && (
                  <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                    {msg.reasoning}
                  </div>
                )}
                {/* 时序交叉：每段思考紧跟其触发的工具调用卡；命令类工具（Bash 等）
                    合并为终端面板（P2 对话内嵌终端，2026-10-23） */}
                {(() => {
                  const segs: { kind: 'card' | 'terminal'; items: typeof msg.toolCalls }[] = []
                  for (const tc of msg.toolCalls || []) {
                    const last = segs[segs.length - 1]
                    const isT = isTerminalCall(tc)
                    if (isT && last?.kind === 'terminal') last.items!.push(tc)
                    else if (isT) segs.push({ kind: 'terminal', items: [tc] })
                    else if (last?.kind === 'card') last.items!.push(tc)
                    else segs.push({ kind: 'card', items: [tc] })
                  }
                  return segs.map((seg, si) => {
                    if (seg.kind === 'terminal') {
                      const reasonings = seg.items!.filter((tc) => tc.reasoning).map((tc) => tc.reasoning!)
                      return (
                        <div key={`t${si}`}>
                          {reasonings.map((r, ri) => (
                            <div key={ri} style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 160, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                              {r}
                            </div>
                          ))}
                          <TerminalView calls={seg.items!} />
                        </div>
                      )
                    }
                    return seg.items!.map((tc, j) => (
                      <div key={`c${si}-${j}`}>
                        {tc.reasoning && (
                          <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 160, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                            {tc.reasoning}
                          </div>
                        )}
                        <ToolCallCard call={tc} />
                      </div>
                    ))
                  })
                })()}
                {/* 最终思考：无后续工具调用时的收尾推理（回答前） */}
                {msg.finalReasoning && (
                  <div style={{ marginTop: 6, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: 160, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                    {msg.finalReasoning}
                  </div>
                )}
              </details>
            ) : null}
            {/* HTML 直渲（2026-10-26）：流式期间走纯 markdown（逐 token 正则切分有
                性能成本），完成后按段切分——```html 围栏与完整 HTML 文档进沙箱
                iframe 渲染，其余照旧 Markdown */}
            {(loading && isLast) ? (
              <MarkdownContent content={msg.content} onImageExpand={setExpandedImage} />
            ) : (
              splitSpecialBlocks(msg.content).map((seg, si) => (
                seg.type === 'html' ? (
                  <InlineHtmlFrame key={si} html={seg.value} />
                ) : seg.type === 'mermaid' ? (
                  <MermaidBlock key={si} code={seg.value} />
                ) : seg.type === 'svg' ? (
                  <SvgBlock key={si} code={seg.value} />
                ) : (
                  <MarkdownContent key={si} content={seg.value} onImageExpand={setExpandedImage} />
                )
              ))
            )}
            {/* 流式打字光标（通用 AI 对话方案，2026-10-25）：生成中文本末尾闪烁 */}
            {loading && isLast && !!msg.content && !msg.error && (
              <span className="stream-cursor" aria-hidden="true" />
            )}
            {msg.error && (
              <div style={{
                marginTop: 8, padding: '8px 12px', borderRadius: 8,
                background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                fontSize: 12.5, color: 'var(--text-secondary)',
                display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
              }}>
                <span style={{ flex: 1, wordBreak: 'break-word' }}>{msg.error}</span>
                <button onClick={() => onRegenerate?.(index)}
                  title="重试" aria-label="重试"
                  style={{
                    padding: '4px 12px', borderRadius: 6, border: '1px solid var(--accent)',
                    background: 'transparent', color: 'var(--accent)', cursor: 'pointer',
                    fontSize: 12, flexShrink: 0,
                  }}>重试</button>
              </div>
            )}
            {msg.complianceWarning && (
              <div style={{
                marginTop: 8, padding: '8px 12px', borderRadius: 8,
                background: 'var(--warning-soft)', border: '1px solid var(--warning)',
                fontSize: 12.5, color: 'var(--warning)',
              }}>
                本条回复已触发内容安全审核，平台正在人工复核（《生成式AI服务管理暂行办法》第 15 条）。
              </div>
            )}
            {msg.stopped && !msg.content && (
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>已停止</div>
            )}
            {msg.stopped && msg.content && (
              <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>— 已停止生成 —</div>
            )}
            {msg.pageLink && (
              <div style={{
                display: 'inline-flex', alignItems: 'stretch', marginTop: 6,
                borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)',
                maxWidth: '100%', background: 'var(--bg-input)',
              }}>
                {onOpenPanel ? (
                  // 统一入口形态（2026-10-17 用户拍板）：所有子页面链接点击
                  // 均在对话内浮窗/浮层打开（桌面浮窗可拖动缩放/移动全屏浮层）；
                  // 修饰键点击放行浏览器默认（新标签/直接访问独立路由）
                  <a href={msg.pageLink}
                    onClick={(e) => {
                      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
                      e.preventDefault()
                      e.stopPropagation()
                      onOpenPanel(msg.pageLink!)
                    }}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px',
                      background: agent?.color || 'var(--accent)',
                      color: '#fff', fontSize: 12, fontWeight: 500, textDecoration: 'none',
                      transition: 'opacity 0.15s', flexShrink: 0,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >{msg.pageLink.includes('/agent/dashboard') || msg.pageLink.includes('/agent/board') ? <BarChartIcon size={13} /> : msg.pageLink.includes('/agent/automation') ? <BotIcon size={13} /> : msg.pageLink.includes('/planet') ? <PlanetIcon size={13} /> : <ClipboardIcon size={13} />} 打开面板</a>
                ) : (
                  <Link to={msg.pageLink}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px',
                      background: agent?.color || 'var(--accent)',
                      color: '#fff', fontSize: 12, fontWeight: 500, textDecoration: 'none',
                      transition: 'opacity 0.15s', flexShrink: 0,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >{msg.pageLink.includes('/agent/dashboard') || msg.pageLink.includes('/agent/board') ? <BarChartIcon size={13} /> : msg.pageLink.includes('/agent/automation') ? <BotIcon size={13} /> : msg.pageLink.includes('/planet') ? <PlanetIcon size={13} /> : <ClipboardIcon size={13} />} 打开面板</Link>
                )}
                {/* 独立页面链接明文显示（同框右侧；点击复制，可直接浏览器打开/收藏） */}
                <button onClick={(e) => {
                  e.stopPropagation()
                  navigator.clipboard.writeText(window.location.origin + msg.pageLink)
                    .then(() => setCopiedLink(true))
                    .catch(() => {})
                  setTimeout(() => setCopiedLink(false), 1500)
                }}
                  className="yuan-tip" data-tip="点击复制此链接（可直接浏览器打开）"
                  title="复制页面链接" aria-label="复制页面链接"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px',
                    color: 'var(--text-secondary)', fontSize: 11, cursor: 'pointer', lineHeight: 1,
                    fontFamily: 'monospace', minWidth: 0, background: 'transparent', border: 'none',
                    borderLeft: '1px solid var(--border)',
                  }}>
                  {copiedLink ? <CheckIcon size={12} /> : <LinkIcon size={11} />}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{msg.pageLink}</span>
                </button>
              </div>
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
