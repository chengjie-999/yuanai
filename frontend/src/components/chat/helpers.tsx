import { useState, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import { getToken } from '../../api'

export type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string }

export function addToken(url: string): string {
  if (url.startsWith('data:')) return url
  if (!url.startsWith('/api/v1/')) return url
  if (url.includes('?token=')) return url
  return `${url}?token=${getToken()}`
}

export function stripMarkdown(text: string): string {
  return text
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`{1,3}[^`]*`{1,3}/g, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/>\s+/g, '')
    .replace(/[-*+]\s+/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function downloadChat(messages: ChatMessage[], filename: string) {
  const text = messages
    .map((m) => {
      const role = m.role === 'user' ? 'You' : 'AI'
      const content = m.role === 'assistant' ? stripMarkdown(m.content) : m.content
      return `[${role}]\n${content}\n`
    })
    .join('\n---\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function encodeMsg(m: any) {
  const meta: any = {}
  if (m.sender && m.sender !== 'orchestrator') meta.s = m.sender
  if (m.toolCalls?.length) meta.t = m.toolCalls
  if (m.reasoning) meta.r = m.reasoning
  const content = Object.keys(meta).length > 0
    ? `\x00META\x00${JSON.stringify(meta)}\x00${m.content || ''}`
    : (m.content || '')
  return { role: m.role, content, ...(m.images?.length ? { images: m.images } : {}) }
}

export function timeAgo(dateStr: string): string {
  const now = new Date()
  const d = new Date(dateStr)
  const diffMs = now.getTime() - d.getTime()
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffDays < 1) {
    if (d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) return '今天'
    return '昨天'
  }
  if (diffDays < 2) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}月前`
  return `${Math.floor(diffDays / 365)}年前`
}

export function groupSessions(sessions: SessionInfo[]): { label: string; items: SessionInfo[] }[] {
  const groups: { label: string; items: SessionInfo[] }[] = []
  let currentLabel = ''
  let currentGroup: SessionInfo[] = []

  for (const s of sessions) {
    const label = timeAgo(s.create_time)
    if (label !== currentLabel) {
      if (currentGroup.length > 0) groups.push({ label: currentLabel, items: currentGroup })
      currentLabel = label
      currentGroup = []
    }
    currentGroup.push(s)
  }
  if (currentGroup.length > 0) groups.push({ label: currentLabel, items: currentGroup })
  return groups
}

export function LoadingDots() {
  const [dots, setDots] = useState('')
  useEffect(() => {
    const t = setInterval(() => setDots((p) => (p.length >= 3 ? '' : p + '.')), 400)
    return () => clearInterval(t)
  }, [])
  return (
    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 14 }}>
      正在思考<span style={{ letterSpacing: 1 }}>{dots}</span>
    </span>
  )
}
