import { useState, useEffect } from 'react'
import type { ChatMessage } from '../../types'

export type SessionInfo = { session_id: string; title: string; update_time: string; is_special?: boolean }

export const SUGGESTIONS = ['帮我查询今天的天气', '帮我计算 1234 × 5678', '请介绍一下你自己', '帮我分析一段数据']

export function stripMarkdown(text: string): string {
  return text.replace(/#{1,6}\s+/g, '').replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1')
    .replace(/`{1,3}[^`]*`{1,3}/g, '').replace(/```[\s\S]*?```/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/>\s+/g, '').replace(/[-*+]\s+/g, '').replace(/\n{3,}/g, '\n\n').trim()
}

export function downloadChat(messages: ChatMessage[], filename: string) {
  const text = messages.map((m) => {
    const role = m.role === 'user' ? 'You' : 'AI'
    const content = m.role === 'assistant' ? stripMarkdown(m.content) : m.content
    return `[${role}]\n${content}\n`
  }).join('\n---\n')
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export function LoadingDots() {
  const [dots, setDots] = useState('')
  useEffect(() => {
    const t = setInterval(() => setDots((p) => (p.length >= 3 ? '' : p + '.')), 400)
    return () => clearInterval(t)
  }, [])
  return <span style={{ color: '#999', fontStyle: 'italic', fontSize: 14 }}>正在输入<span style={{ letterSpacing: 1 }}>{dots}</span></span>
}
