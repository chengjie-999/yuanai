import { useState, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import { API_BASE, getToken } from '../../api'

export type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string; is_main?: boolean }

export function addToken(url: string): string {
  if (url.startsWith('data:')) return url
  if (!url.startsWith('/api/v1/')) return url
  if (url.includes('?token=')) return url
  if (url.startsWith('/api/v1/chat/image')) return url  // 图片路由公开，加 token 会击穿 immutable 缓存
  return `${url}?token=${getToken()}`
}

/** 取 5 秒短期 sse token（iframe 加载 HTML 资源用，替代长期 JWT 拼 URL） */
export async function fetchSseToken(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/auth/sse-token`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) return ''
    return ((await res.json()) as { token?: string }).token || ''
  } catch {
    return ''
  }
}

/**
 * iframe 安全 URL：/api/v1 资源换 5 秒 sse_token（URL 不落 7 天 JWT，S1.2）。
 * data: 与公开路由（chat/image）跳过；sse token 获取失败时回退长期 token
 * （iframe 已加 sandbox="allow-scripts" + 后端 CSP 沙箱头，双重兜底）。
 */
export function useSecuredUrl(url: string): string {
  const [final, setFinal] = useState(url)
  useEffect(() => {
    let alive = true
    if (!url || url.startsWith('data:') || !url.startsWith('/api/v1/')
      || url.startsWith('/api/v1/chat/image') || url.includes('?token=')) {
      setFinal(url)
      return
    }
    fetchSseToken().then((tok) => {
      if (!alive) return
      if (tok) setFinal(`${url}${url.includes('?') ? '&' : '?'}token=${tok}`)
      else setFinal(`${url}?token=${getToken()}`)  // 端点异常时退回现状（沙箱内）
    }).catch(() => {})
    return () => { alive = false }
  }, [url])
  return final
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
  if (m.pageLink) meta.p = m.pageLink
  // 信封新增短键（与后端 message.py 对偶）：recipient→rp / turn→tn / msgType→ty
  if (m.recipient) meta.rp = m.recipient
  if (m.turn) meta.tn = m.turn
  if (m.msgType && m.msgType !== 'chat') meta.ty = m.msgType
  // P1-1：错误/停止标记（前端状态持久化；META 短键 e=错误文案 / sp=停止）
  if (m.error) meta.e = m.error
  if (m.stopped) meta.sp = 1
  const content = Object.keys(meta).length > 0
    ? `\x00META\x00${JSON.stringify(meta)}\x00${m.content || ''}`
    : (m.content || '')
  // 顶层信封字段一并返回（/chat/save 落列用；META 内容保持向后兼容）
  return {
    role: m.role, content,
    ...(m.images?.length ? { images: m.images } : {}),
    ...(m.sender ? { sender: m.sender } : {}),
    ...(m.recipient ? { recipient: m.recipient } : {}),
    ...(m.turn ? { turn: m.turn } : {}),
    ...(m.msgType && m.msgType !== 'chat' ? { type: m.msgType } : {}),
  }
}

/** 将会话消息转为包含工具调用上下文的历史记录（传给模型用）
 * 注意：tool 消息必须紧跟带 tool_calls 的 assistant 消息，否则云端 API 400 拒绝
 *
 * 信封协议（多智能体身份）：正文不再注入【xx】前缀——说话人身份走信封字段
 * （sender/recipient/turn/type），模型上下文的视图滤波由后端 views.py 完成。
 */
export function buildHistoryWithToolContext(messages: ChatMessage[]): { role: string; content: string; tool_calls?: any[]; tool_call_id?: string; sender?: string; recipient?: string; turn?: number; type?: string }[] {
  const result: { role: string; content: string; tool_calls?: any[]; tool_call_id?: string; sender?: string; recipient?: string; turn?: number; type?: string }[] = []

  for (const m of messages) {
    const env = {
      ...(m.sender ? { sender: m.sender } : {}),
      ...(m.recipient ? { recipient: m.recipient } : {}),
      ...(m.turn ? { turn: m.turn } : {}),
      ...(m.msgType && m.msgType !== 'chat' ? { type: m.msgType } : {}),
    }
    if (m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0) {
      // assistant 决策消息 + 对应的 tool_calls 列表（保证 tool 消息有合法归属）
      const toolNames = m.toolCalls.map(tc => tc.name).join(', ')
      const calls = m.toolCalls.map((tc, i) => ({
        id: `hist_${i}`, type: 'function', function: { name: tc.name, arguments: '{}' },
      }))
      result.push({ role: 'assistant', content: `[决定调用工具: ${toolNames}]`, tool_calls: calls, ...env })

      // 每个 tool_call 都必须有一条 tool 结果消息（未完成/出错也占位）；
      // 工具结果信封：sender 继承所属 assistant，type=tool_result
      const toolEnv = { sender: m.sender, type: 'tool_result' }
      m.toolCalls.forEach((tc, i) => {
        if (tc.status === 'done') {
          const summary = (tc.result || '完成').slice(0, 800)
          result.push({ role: 'tool', content: `工具 ${tc.name} 执行结果:\n${summary}`, tool_call_id: `hist_${i}`, ...toolEnv })
        } else if (tc.status === 'error') {
          result.push({ role: 'tool', content: `工具 ${tc.name} 执行出错: ${tc.result || '未知错误'}`, tool_call_id: `hist_${i}`, ...toolEnv })
        } else {
          result.push({ role: 'tool', content: `工具 ${tc.name} 未完成`, tool_call_id: `hist_${i}`, ...toolEnv })
        }
      })

      // 最后是助手的实际回复
      result.push({ role: 'assistant', content: m.content || '', ...env })
    } else {
      result.push({ role: m.role, content: m.content || '', ...env })
    }
  }

  return result
}

/** 朗读文本口语化：markdown 结构替换为口语占位、噪音符号剔除、标点归一（P6 语调优化） */
export function toSpeechText(text: string): string {
  let t = stripMarkdown(text)
  // 代码块整体被 stripMarkdown 吃掉 → 用口语占位替代（原文先替换再 strip）
  t = text
    .replace(/```[\s\S]*?```/g, '（这里有一段代码）')
    .replace(/`[^`]*`/g, '')
  t = stripMarkdown(t)
  // 表格残留行（含 | 分隔）→ 口语占位
  t = t.split('\n').map((ln) => (/^\s*\|.*\|\s*$/.test(ln) ? '（这里有一张表格）' : ln)).join('\n')
  // 裸 URL → （链接）
  t = t.replace(/https?:\/\/[^\s)\]]+/g, '（链接）')
  // emoji / 装饰符号剔除
  t = t.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '')
  // 连续标点归一
  t = t.replace(/([。！？!?；;，,])\1+/g, '$1')
  t = t.replace(/\s*\n+\s*/g, '。')  // 换行 → 句号停顿
  t = t.replace(/。{2,}/g, '。')
  // 句末缺标点补句号
  const trimmed = t.trim().replace(/。$/g, '')
  return trimmed ? trimmed.replace(/([^。！？!?；;])$/u, '$1。') : ''
}

/** 朗读分段：按句切分贪心合并到 ≤max 字（超长单句硬切），返回段落数组 */
export function splitSpeechSegments(text: string, max = 200): string[] {
  const sentences = text.split(/(?<=[。！？!?；;\n])/).map((s) => s.trim()).filter(Boolean)
  const segments: string[] = []
  let cur = ''
  for (let s of sentences) {
    while (s.length > max) {
      if (cur) { segments.push(cur); cur = '' }
      segments.push(s.slice(0, max))
      s = s.slice(max)
    }
    if (cur.length + s.length > max) {
      segments.push(cur)
      cur = s
    } else {
      cur += s
    }
  }
  if (cur) segments.push(cur)
  return segments.length ? segments : [text.slice(0, max)]
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
    // 按最后活跃时间分组：旧会话发新消息后跳到「今天」组置顶（后端已按 update_time 排序）
    const label = timeAgo(s.update_time || s.create_time)
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
