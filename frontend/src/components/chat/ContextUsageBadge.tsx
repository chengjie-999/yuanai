import { useEffect, useState, useSyncExternalStore } from 'react'
import { API_BASE, authHeaders } from '../../api'
import { fmtTokens } from './helpers'

/* 上下文用量徽标（2026-11-06，Claude Code /context 风格）：
   顶栏常显——当前会话将发给模型的 token 估算 vs 模型窗口（后端
   /chat/context-usage，与 /stream 组装口径对齐）。当前会话 id 由
   ChatPage 写入模块级 store（跨组件共享）；消息落库后 ChatPage 发
   yuan-ctx-refresh 事件即时刷新，20s 兜底轮询。 */

let _currentSid = ''
const _listeners = new Set<() => void>()

/** ChatPage 挂载时写入当前会话 id（切换/进入会话即刷新徽标） */
export function setContextSid(sid: string) {
  if (_currentSid !== sid) {
    _currentSid = sid
    _listeners.forEach((l) => l())
  }
}

function _subscribe(l: () => void) {
  _listeners.add(l)
  return () => { _listeners.delete(l) }
}
const _getSnapshot = () => _currentSid

type CtxData = {
  used: number; limit: number; percent: number
  model: string; history_capped: number; truncated: boolean
}

export default function ContextUsageBadge() {
  const sid = useSyncExternalStore(_subscribe, _getSnapshot)
  const [data, setData] = useState<CtxData | null>(null)

  useEffect(() => {
    if (!sid) { setData(null); return }
    let alive = true
    const load = () => {
      fetch(`${API_BASE}/chat/context-usage?sid=${encodeURIComponent(sid)}`, { headers: authHeaders() })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: CtxData | null) => { if (alive && d) setData(d) })
        .catch(() => {})
    }
    load()
    window.addEventListener('yuan-ctx-refresh', load)
    const timer = setInterval(load, 20000)
    return () => {
      alive = false
      window.removeEventListener('yuan-ctx-refresh', load)
      clearInterval(timer)
    }
  }, [sid])

  if (!sid || !data) return null
  const pct = Math.min(100, Math.max(0, data.percent))
  const color = pct >= 85 ? 'var(--danger)' : pct >= 60 ? 'var(--warning)' : 'var(--success)'
  const tip = `上下文用量：${fmtTokens(data.used)} / ${fmtTokens(data.limit)} tokens`
    + `（最近 ${data.history_capped} 条${data.truncated ? '，更早的对话已整理进长期记忆' : ''}）`
  return (
    <div className="yuan-tip yuan-tip-down" data-tip={tip} aria-label={tip}
      style={{
        display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px',
        borderRadius: 999, border: '1px solid var(--border-light)',
        background: 'var(--bg-primary)', fontSize: 11, color: 'var(--text-secondary)',
        whiteSpace: 'nowrap', cursor: 'default', flexShrink: 0, lineHeight: 1.4,
      }}>
      <span>上下文</span>
      <span style={{ fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>
      <span style={{ width: 28, height: 3, borderRadius: 2, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
        <span style={{
          display: 'block', width: `${pct}%`, height: '100%',
          background: color, transition: 'width 0.3s',
        }} />
      </span>
    </div>
  )
}
