import { useState, useEffect } from 'react'
import type { ChatMessage } from '../../types'
import { API_BASE, authHeaders, getToken } from '../../api'

export type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string; is_main?: boolean; agent_kind?: string }

/* token 数展示（2026-11-06 用量脚注/上下文徽标）：≥1000 → 1.2K 形态 */
export function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n)
}

/* 小额成本展示（2026-11-06 用量脚注）：≥0.01 两位小数，更小保留两位有效数字 */
export function fmtCostSmall(v: number): string {
  return v >= 0.01 ? v.toFixed(2) : String(Number(v.toPrecision(2)))
}

export function addToken(url: string): string {
  if (url.startsWith('data:')) return url
  if (!url.startsWith('/api/v1/')) return url
  if (url.includes('?token=')) return url
  // C3（2026-10-29）：聊天图片已改鉴权（?token=JWT；URL 随登录会话稳定，
  // 缓存按 token 键控，登录态不变则命中不变）
  return `${url}?token=${getToken()}`
}

/** 取 5 秒短期 sse token（iframe 加载 HTML 资源用，替代长期 JWT 拼 URL） */
export async function fetchSseToken(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/auth/sse-token`, {
      headers: authHeaders(),
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

/* 下载版品牌页脚（2026-11-14 用户拍板「下载的 html 有入口」）：仅在下载路径注入——
   渲染保持模型代码原样；模型已写官网链接/已有页脚则跳过（幂等不重复） */
export function injectBrandFooter(html: string): string {
  if (!html || html.includes('xiaoyuan-brand-footer') || html.includes('cjyuanai.cn')) return html
  const footer = `
<div class="xiaoyuan-brand-footer" style="position:fixed;bottom:0;left:0;right:0;z-index:9999;background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;text-align:center;padding:5px 12px;font-family:'PingFang SC','Microsoft YaHei',sans-serif;font-size:12px;box-shadow:0 -2px 8px rgba(15,23,42,0.12);">
  由 <a href="https://cjyuanai.cn/" target="_blank" style="color:#fff;font-weight:700;text-decoration:underline;">小元AI</a> 生成 · 云边协同 · 对话即执行 · <a href="https://cjyuanai.cn/" target="_blank" style="color:#fff;text-decoration:underline;">打开官网</a>
</div>
<style>body{padding-bottom:44px;}</style>`
  const idx = html.search(/<\/body>/i)
  if (idx >= 0) return html.slice(0, idx) + footer + html.slice(idx)
  return html + footer
}

/* ============ 统一下载工具（2026-11-14 收敛，唯一实现点） ============ */

/** 统一文件下载：Blob + a[download] 零依赖——HTML/SVG/PNG/聊天记录全部走这里 */
export function downloadBlob(filename: string, content: string | Blob, mime: string) {
  const blob = typeof content === 'string' ? new Blob([content], { type: mime }) : content
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** 下载文件名时间戳：2026-11-14-15-30-20 形态 */
export function downloadTs(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}-${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`
}

/** SVG 渲染成 PNG（canvas，2x 清晰度）——微信/Windows 双击打不开 SVG 的通用兜底。
    返回 null = 转换失败（svg 含外部资源致 canvas 污染等）。 */
export function svgToPngBlob(svg: string): Promise<Blob | null> {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
    img.onload = () => {
      try {
        const w = img.naturalWidth || 800
        const h = img.naturalHeight || 600
        const scale = 2
        const canvas = document.createElement('canvas')
        canvas.width = w * scale
        canvas.height = h * scale
        const ctx = canvas.getContext('2d')
        if (!ctx) { resolve(null); return }
        ctx.scale(scale, scale)
        ctx.drawImage(img, 0, 0, w, h)
        canvas.toBlob((b) => resolve(b), 'image/png')
      } catch { resolve(null) } finally {
        URL.revokeObjectURL(url)
      }
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve(null) }
    img.src = url
  })
}

export function downloadChat(messages: ChatMessage[], filename: string) {
  // C5 AI 标识（2026-10-29）：导出文件头部显式声明（《标识办法》第 4 条）
  const AIGC_HEADER = '【说明】本对话记录中的 AI 回复均由人工智能生成，仅供参考，请自行核实重要信息。\n\n'
  const text = messages
    .map((m) => {
      const role = m.role === 'user' ? 'You' : 'AI'
      const content = m.role === 'assistant' ? stripMarkdown(m.content) : m.content
      return `[${role}]\n${content}\n`
    })
    .join('\n---\n')
  downloadBlob(filename, AIGC_HEADER + text, 'text/plain;charset=utf-8')
}

/** 新消息 id 单一生成点（2026-11-18 起：创建即赋，不再等保存时才补——
    保存时才 encodeMsg 补 id 曾是「整段对话重复 12 遍」事故的一环：
    X5 无 crypto.randomUUID，每次保存生成的 id 不稳定） */
export function newMsgId(): string {
  return (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID() : `m${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function encodeMsg(m: any) {
  // #30：历史消息透传已有 id；兜底补 id（旧数据/第三方构造）——保存幂等/同步 diff 的键
  if (!m.msg_id) m.msg_id = newMsgId()
  const meta: any = {}
  if (m.sender && m.sender !== 'orchestrator') meta.s = m.sender
  if (m.toolCalls?.length) meta.t = m.toolCalls
  if (m.reasoning) meta.r = m.reasoning
  if (m.finalReasoning) meta.fr = m.finalReasoning
  if (m.pageLink) meta.p = m.pageLink
  // 信封新增短键（与后端 message.py 对偶）：recipient→rp / turn→tn / msgType→ty
  if (m.recipient) meta.rp = m.recipient
  if (m.turn) meta.tn = m.turn
  if (m.msgType && m.msgType !== 'chat') meta.ty = m.msgType
  // P1-1：错误/停止标记（前端状态持久化；META 短键 e=错误文案 / sp=停止）
  if (m.error) meta.e = m.error
  if (m.stopped) meta.sp = 1
  if (m.truncated) meta.tr = 1  // U4 继续生成
  // 多窗口 #16：委派任务卡摘要 → 执行窗口会话引用（w=session / wk=kind）
  if (m.windowSession) meta.w = m.windowSession
  if (m.windowKind) meta.wk = m.windowKind
  // B0：交互图表 URL 持久化（META 短键 h=htmls 数组；此前刷新即丢）
  if (m.htmls?.length) meta.h = m.htmls
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
    ...(m.msg_id ? { msg_id: m.msg_id } : {}),
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
  // 表格残留行（含 | 分隔）→ 口语占位；连续表格行合并为一句
  // （2026-11-14 修复：此前每行一句，一张 N 行表格会连读 N 遍「这里有一张表格」）
  t = t.split('\n').reduce<string[]>((acc, ln) => {
    if (/^\s*\|.*\|\s*$/.test(ln)) {
      if (!acc.length || acc[acc.length - 1] !== '（这里有一张表格）') acc.push('（这里有一张表格）')
      return acc
    }
    acc.push(ln)
    return acc
  }, []).join('\n')
  // 裸 URL → （链接）
  t = t.replace(/https?:\/\/[^\s)\]]+/g, '（链接）')
  // HTML 标签（模型输出里的 <br>/<div>/<span> 等，乱读来源之一）
  t = t.replace(/<[^>]+>/g, '')
  // 有序列表序号（"1. " "2、" "3）"）——数字序号读出来是噪音
  t = t.replace(/^\s*\d+\s*[.、)）]\s*/gm, '')
  // 多余空白归一（中文间多空格/制表符）
  t = t.replace(/[ \t]+/g, ' ')
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

/** 后端时间串解析（加固：iOS Safari 对 "YYYY-MM-DD HH:MM:SS" 空格分隔的
    new Date 解析返回 Invalid Date——正则手动拆解，全端一致） */
function parseServerTime(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(s)
  if (!m) return null
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0))
}

/** 消息时间分隔线文案（2026-11-18 用户「加上时间」）：相邻消息间隔 ≥5 分钟
    时返回微信式标签（今天 HH:MM / 昨天 HH:MM / M月D日 HH:MM），否则返回 ''
    不渲染。create_time 是后端换算好的北京时间字符串 */
export function timeDividerLabel(prev: ChatMessage | undefined, cur: ChatMessage | undefined): string {
  if (!prev?.create_time || !cur?.create_time) return ''
  const p = parseServerTime(prev.create_time)
  const c = parseServerTime(cur.create_time)
  if (!p || !c) return ''
  if (c.getTime() - p.getTime() < 5 * 60000) return ''
  const hm = `${String(c.getHours()).padStart(2, '0')}:${String(c.getMinutes()).padStart(2, '0')}`
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const now = new Date()
  if (sameDay(c, now)) return `今天 ${hm}`
  if (sameDay(c, new Date(now.getTime() - 86400000))) return `昨天 ${hm}`
  return `${c.getMonth() + 1}月${c.getDate()}日 ${hm}`
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
      正在回复<span style={{ letterSpacing: 1 }}>{dots}</span>
    </span>
  )
}

/* 从回复正文中切分 HTML 渲染段（2026-10-26）：完整 HTML 文档或 ```html 围栏块
   独立成段交给沙箱 iframe 渲染，其余仍走 Markdown。 */
export interface ContentSegment {
  type: 'md' | 'html' | 'mermaid' | 'svg'
  value: string
}

const _HTML_DOC_RE = /<!DOCTYPE html[\s\S]*?<\/html>|<html[\s>][\s\S]*?<\/html>/gi
const _FENCE_RE = /```(html|mermaid|svg)\s*\n([\s\S]*?)```/g

export function splitSpecialBlocks(content: string): ContentSegment[] {
  if (!content) return []
  const segments: ContentSegment[] = []
  let last = 0
  // 围栏块与完整文档统一按位置合并处理：先收集所有匹配区间
  const spans: { start: number; end: number; html: string; full: boolean; lang?: string }[] = []
  for (const m of content.matchAll(_HTML_DOC_RE)) {
    const i = m.index ?? 0
    spans.push({ start: i, end: i + m[0].length, html: m[0], full: true })
  }
  for (const m of content.matchAll(_FENCE_RE)) {
    const i = m.index ?? 0
    const lang = m[1].toLowerCase()
    spans.push({ start: i, end: i + m[0].length, html: m[2], full: false, lang })
  }
  if (!spans.length) return [{ type: 'md', value: content }]
  spans.sort((a, b) => a.start - b.start)
  for (const s of spans) {
    if (s.start < last) continue  // 重叠区间跳过（围栏在文档内的情形）
    if (s.start > last) segments.push({ type: 'md', value: content.slice(last, s.start) })
    segments.push({ type: (s.lang === 'mermaid' || s.lang === 'svg') ? s.lang : 'html', value: s.html })
    last = s.end
  }
  if (last < content.length) segments.push({ type: 'md', value: content.slice(last) })
  return segments.filter((s) => s.value.trim())
}
