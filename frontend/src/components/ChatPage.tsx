import { useState, useRef, useEffect, useCallback, lazy, Suspense } from 'react'
import { streamChat, createSession, listSessions, ensureMainSession, deleteSession, renameSession, loadMessages, saveMessages, loadFeedback, setFeedback, reportMessage, getStoredModel, getStoredEffort, API_BASE, getToken, authHeaders, shareSession, fetchUserPrefs, putUserPrefs } from '../api'
import type { ChatMessage } from '../types'
import { senderFromTool, AGENT_CONFIG, WINDOW_AGENTS } from '../config/agents'
import { encodeMsg, newMsgId, buildHistoryWithToolContext } from './chat/helpers'
import { setContextSid } from './chat/ContextUsageBadge'
import Modal from './Modal'
import Sidebar from './chat/Sidebar'
import ChatView from './chat/ChatView'
import VoiceCall from './chat/VoiceCall'
import ZoomableImage from './chat/ZoomableImage'
import { useVoiceCall } from './chat/useVoiceCall'
import { useAutoRead, setAutoReadValue } from '../hooks/useAutoRead'
import { useAnswerTone, playAnswerTone } from '../hooks/useAnswerTone'
import { useTheme } from '../contexts/ThemeContext'
import { ChevronLeftIcon, ChevronRightIcon, ArrowLeftIcon, LinkIcon } from './icons'

// 子页面懒加载（对话内浮窗/浮层宿主，统一入口形态 2026-10-17）
const PlanPageLazy = lazy(() => import('../pages/PlanPage'))
const AgentAnalysisLazy = lazy(() => import('../pages/AgentAnalysisPage'))
const AgentAutomationLazy = lazy(() => import('../pages/AgentAutomationPage'))
const AgentKnowledgeLazy = lazy(() => import('../pages/AgentKnowledgePage'))
const MedicalLazy = lazy(() => import('../components/MedicalPage'))
const RecordsLazy = lazy(() => import('../components/CollectionRecordsPage'))
const BoardLazy = lazy(() => import('../pages/DashboardBoardPage'))
const DashboardLazy = lazy(() => import('../pages/AnalysisDashboard'))
const RfmLazy = lazy(() => import('../pages/RFMDashboard'))
const PlanetLazy = lazy(() => import('../pages/PlanetPage'))
const BillingLazy = lazy(() => import('./BillingPage'))
const SettingsLazy = lazy(() => import('./SettingsPage'))

// 页面路径 → 懒加载组件 + 标题（浮窗/浮层标题栏与地址栏用）
function resolvePanel(path: string): { Comp: any; props: any; title: string } | null {
  if (!path) return null
  if (path.split('?')[0] === '/settings') return { Comp: SettingsLazy, props: {}, title: '对话设置' }
  if (path.split('?')[0] === '/chat/plan') return { Comp: PlanPageLazy, props: {}, title: '计划面板' }
  if (path.startsWith('/chat/agent/dashboard/')) return { Comp: DashboardLazy, props: { sessionId: path.split('/').pop() }, title: '分析大屏' }
  if (path.startsWith('/chat/agent/board/')) return { Comp: BoardLazy, props: { boardKey: path.split('/').pop() }, title: '分析看板' }
  if (path.startsWith('/chat/agent/analysis')) return { Comp: AgentAnalysisLazy, props: {}, title: '数据分析' }
  if (path.startsWith('/chat/agent/automation')) return { Comp: AgentAutomationLazy, props: {}, title: '自动化' }
  if (path.startsWith('/chat/agent/knowledge')) return { Comp: AgentKnowledgeLazy, props: {}, title: '知识库' }
  if (path.startsWith('/chat/agent/medical')) return { Comp: MedicalLazy, props: {}, title: '医学工作台' }
  if (path.startsWith('/chat/agent/records')) return { Comp: RecordsLazy, props: {}, title: '采集记录' }
  if (path.startsWith('/chat/agent/rfm')) return { Comp: RfmLazy, props: {}, title: 'RFM 大屏' }
  if (path.startsWith('/chat/planet')) return { Comp: PlanetLazy, props: {}, title: '知识星球' }
  if (path.startsWith('/chat/billing')) return { Comp: BillingLazy, props: {}, title: '充值中心' }
  return null
}

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string; is_main?: boolean; agent_kind?: string }

/* 兼容历史消息：路由迁移后旧路径 /agent/... 顶层已不存在（会落到兜底路由跳首页），渲染时统一补 /chat 前缀 */
function normalizePageLink(p: any): string | undefined {
  if (typeof p === 'string' && p.startsWith('/agent') && !p.startsWith('/chat')) return '/chat' + p
  return p
}

/* 历史消息解析：信封读取优先级 服务端列 > \x00META\x00 短键 > 缺省（新旧数据兼容） */
function parseHistory(history: any[]): ChatMessage[] {
  return history.map((m: any) => {
    let sender: any = undefined
    let toolCalls: any = undefined
    let reasoning: string | undefined
    let finalReasoning: string | undefined
    let pageLink: string | undefined
    let recipient: string | undefined = undefined
    let turn: number | undefined = undefined
    let msgType: any = undefined
    let error: string | undefined
    let stopped: boolean | undefined
    let htmls: string[] | undefined
    let truncated: boolean | undefined
    let windowSession: string | undefined
    let windowKind: any = undefined
    let content = m.content || ''
    if (typeof content === 'string' && content.startsWith('\x00META\x00')) {
      const end = content.indexOf('\x00', 6)
      if (end > 6) {
        try {
          const meta = JSON.parse(content.substring(6, end))
          sender = meta.s; toolCalls = meta.t; reasoning = meta.r
          finalReasoning = meta.fr
          pageLink = normalizePageLink(meta.p)
          recipient = meta.rp; turn = meta.tn; msgType = meta.ty
          if (meta.e) error = meta.e
          if (meta.sp) stopped = true
          if (meta.h) htmls = meta.h
          if (meta.tr) truncated = true
          // 多窗口 #16：委派任务卡摘要 → 执行窗口会话引用
          if (meta.w) windowSession = meta.w
          if (meta.wk) windowKind = meta.wk
        } catch {}
        content = content.substring(end + 1)
      }
    }
    // 服务端列（迁移 0014 后）优先于 META 短键
    if (m.sender) sender = m.sender
    if (m.recipient) recipient = m.recipient
    if (m.turn) turn = m.turn
    if (m.type) msgType = m.type
    return { role: m.role, content, images: m.images, sender, toolCalls,
             reasoning, finalReasoning, pageLink, recipient, turn, msgType, error, stopped, htmls, truncated,
             windowSession, windowKind, msg_id: m.msg_id || undefined,
             create_time: m.create_time || undefined }
  })
}

export default function ChatPage({ user }: { user?: any }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSid, setCurrentSid] = useState<string>('')
  // 上下文用量徽标（2026-11-06）：当前会话 id 写入模块级 store → 顶栏徽标
  // 跟随会话切换刷新
  useEffect(() => { setContextSid(currentSid) }, [currentSid])
  // 挂载失败兜底（2026-10-22 欢迎页移除后：加载中不再闪欢迎页，接口异常给重试框）
  const [initFailed, setInitFailed] = useState(false)
  // sweep 审查修复：历史加载失败态（区别于空会话）——阻断发送防全量替换清历史
  const [loadFailed, setLoadFailed] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState(getStoredModel)
  // 模型/推理强度选择已子页面化（2026-11-14）：状态仅供发送链路读取，
  // 设置页写 localStorage 后由挂载/事件同步
  useEffect(() => {
    const onModelChanged = () => {
      try {
        const v = localStorage.getItem('selectedModel')
        if (v) setModel(v)
      } catch { /* 忽略 */ }
    }
    window.addEventListener('yuan-model-changed', onModelChanged)
    return () => window.removeEventListener('yuan-model-changed', onModelChanged)
  }, [])
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth > 768)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)
  // 微信内置浏览器提示（2026-10-29）：其 SSE 流式兼容差导致长回复截断——
  // 提示一次（localStorage 记录），引导用系统浏览器打开
  const [wxTip, setWxTip] = useState(() => {
    try {
      const isWx = /MicroMessenger/i.test(navigator.userAgent)
      return isWx && localStorage.getItem('wxTipSeen') !== '1'
    } catch { return false }
  })
  const dismissWxTip = () => {
    try { localStorage.setItem('wxTipSeen', '1') } catch { /* 忽略 */ }
    setWxTip(false)
  }
  const [images, setImages] = useState<string[]>([])
  const [expandedImage, setExpandedImage] = useState<string | null>(null)
  // 聊天模式（内部自动切换，不再暴露下拉框——微信式群聊由 @指定接管）：
  // local=本地统筹 Agent（默认）→ 本地离线时自动落 cloud；claude 模式已并入 @Claude Code
  const [chatMode, setChatMode] = useState<'local' | 'cloud' | 'claude'>('local')
  // 娱乐模式（E1）：work 现状 / entertainment 纯云端陪伴式对话——localStorage 持久化；
  // 开启时强制云端（chat_mode=entertainment 后端跳过 Agent 桥接），@指定与聊天模式不可用
  const [entMode, setEntMode] = useState(() => {
    try { return localStorage.getItem('entertainmentMode') === '1' } catch { return false }
  })
  // N3 云端/本地三态（2026-11-06）：auto=本机优先离线回退 / cloud=强制云端 / local=强制本机
  const [chatBackend, setChatBackendState] = useState<'auto' | 'cloud' | 'local'>(() => {
    try { const v = localStorage.getItem('chatBackend'); return v === 'cloud' || v === 'local' ? v : 'auto' } catch { return 'auto' }
  })
  const setChatBackend = (v: 'auto' | 'cloud' | 'local') => {
    setChatBackendState(v)
    try { localStorage.setItem('chatBackend', v) } catch { /* 忽略 */ }
  }
  // 设置页（子页面）切执行位置后同步状态（2026-11-14 子页面化）
  useEffect(() => {
    const onBackendChanged = () => {
      try {
        const v = localStorage.getItem('chatBackend')
        if (v === 'cloud' || v === 'local' || v === 'auto') setChatBackendState(v)
      } catch { /* 忽略 */ }
    }
    window.addEventListener('yuan-backend-changed', onBackendChanged)
    return () => window.removeEventListener('yuan-backend-changed', onBackendChanged)
  }, [])
  const prevChatModeRef = useRef<'local' | 'cloud' | 'claude'>('local')
  const toggleEntMode = async () => {
    const next = !entMode
    // 审查修复：切娱乐模式前先退出执行窗口——用户取消切换则整个不进入
    // （此前先置 entMode 再切窗，guard 取消后切换器已隐藏、困在执行窗口）
    if (next && agentKindRef.current !== 'chat') {
      const ok = await handleSwitchKind('chat')
      if (!ok) return
    }
    setEntMode(next)
    try { localStorage.setItem('entertainmentMode', next ? '1' : '0') } catch { /* 忽略 */ }
    if (next) {
      prevChatModeRef.current = chatMode
      setChatMode('cloud')
      setTargetAgent('')  // 娱乐模式不委派，清掉残留定向
    } else {
      setChatMode(prevChatModeRef.current || 'local')
    }
  }
  // 多智能体窗口 P1（2026-11-13）：当前窗口类型——chat=对话窗口（小元），
  // claude/automation=执行窗口（独立上下文+会话，受统筹监控领导）
  const [agentKind, setAgentKind] = useState<'chat' | 'claude' | 'automation'>('chat')
  const agentKindRef = useRef<'chat' | 'claude' | 'automation'>('chat')
  agentKindRef.current = agentKind
  // 每窗口记住最后打开的会话：切换回来落回原会话（localStorage 持久化）
  const [lastSidByKind, setLastSidByKind] = useState<Record<string, string>>(() => {
    try { return JSON.parse(localStorage.getItem('agentLastSid') || '{}') } catch { return {} }
  })
  const lastSidByKindRef = useRef(lastSidByKind)
  lastSidByKindRef.current = lastSidByKind
  const saveLastSid = (kind: string, sid: string) => {
    setLastSidByKind((prev) => {
      const next = { ...prev, [kind]: sid }
      try { localStorage.setItem('agentLastSid', JSON.stringify(next)) } catch { /* 存储受限，仅本次会话 */ }
      return next
    })
  }
  // @指定智能体（群聊式定向委派；空 = 统筹自行路由；发送后自动复位）
  const [targetAgent, setTargetAgent] = useState('')
  const targetAgentRef = useRef('')
  targetAgentRef.current = targetAgent
  // 长任务小窗：sessionId → 固定定向智能体（该会话内消息持久定向，不占主对话）
  const [dmTargets, setDmTargets] = useState<Record<string, string>>(() => {
    try { return JSON.parse(localStorage.getItem('dmTargets') || '{}') } catch { return {} }
  })
  const dmTargetsRef = useRef(dmTargets)
  dmTargetsRef.current = dmTargets
  // 重新生成只替换本条气泡：其后消息暂存，流结束后按原序回挂（2026-10-25 修复——
  // 此前截断其后所有消息 = 静默数据丢失）
  const pendingAfterRef = useRef<{ sid: string; index: number; after: ChatMessage[] } | null>(null)
  // #30：编辑重发截断的被删消息 id（发送落库时显式删除——替代全量替换的隐式截断）
  const pendingDeletedIdsRef = useRef<string[]>([])
  const saveDmTarget = (sid: string, target: string) => {
    setDmTargets((prev) => {
      const next = target ? { ...prev, [sid]: target } : { ...prev }
      try { localStorage.setItem("dmTargets", JSON.stringify(next)) } catch { /* 存储受限，仅本次会话 */ }
      return next
    })
  }
  // 推理强度：localStorage 持久化（设置页子页面写），仅对 DeepSeek 系列生效
  const [effort, setEffortState] = useState<'low' | 'medium' | 'high'>(getStoredEffort())
  // 设置页切推理强度后同步状态（2026-11-14 子页面化）
  useEffect(() => {
    const onEffortChanged = () => {
      try {
        const v = localStorage.getItem('reasoningEffort')
        if (v === 'low' || v === 'medium' || v === 'high') setEffortState(v)
      } catch { /* 忽略 */ }
    }
    window.addEventListener('yuan-effort-changed', onEffortChanged)
    return () => window.removeEventListener('yuan-effort-changed', onEffortChanged)
  }, [])
  const [localOnline, setLocalOnline] = useState(false)
  const [claudeOnline, setClaudeOnline] = useState(false)
  const [statusKnown, setStatusKnown] = useState(false)
  // P3-5 执行观测面进对话（2026-11-09）：电脑执行状态 15s 轮询——
  // 愿景「手机看电脑在干什么」的对话内闭环（执行中/卡死/空闲 + 最近活动）
  const [ccActivity, setCcActivity] = useState<{ online: boolean; agent_name: string; latest: { message: string; detail: string; ts?: number; time: string } | null; age_s?: number } | null>(null)
  // 多窗口 P3：CC 执行中判定（活动心跳 <60s 且处于工具/思考态）——
  // 「后台执行中」指示条按智能体分组展示
  const ccBusy = claudeOnline && ccActivity?.age_s != null && ccActivity.age_s < 60
    && /工具调用|思考中|等待审批/.test(ccActivity?.latest?.message || '')
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/chat/cc-activity`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (!res.ok) return
        setCcActivity(await res.json())
      } catch { /* 静默：观测面降级不影响对话 */ }
    }
    poll()
    const t = setInterval(poll, 15000)
    return () => clearInterval(t)
  }, [])
  // 多端同步 P0-1（2026-11-09）：当前会话增量轮询——对端设备发的新消息
  // 15s（+ 窗口聚焦/切回立即一次）尾部合入；有进行中 SSE 流时跳过（不打断
  // 本地流式态）；只追加不缩减（对端编辑/重发等缩量场景等手动切会话刷新，
  // 避免误删本端未落库的瞬时气泡如小窗问候语）
  const pollMsgSigRef = useRef<{ sid: string; count: number; tail: string } | null>(null)
  const syncPoll = useCallback(async () => {
    const sid = sidRef.current
    if (!sid || streamRef.current) return  // 流式进行中不合并
    try {
      const history = await loadMessages(sid)
      if (!history) return  // 加载失败（网络/500）：本轮跳过，下轮再试
      const tailMsg = history[history.length - 1]
      const sig = { sid, count: history.length, tail: String(tailMsg?.content || '') }
      const prev = pollMsgSigRef.current
      const local = messagesRef.current
      if (prev && prev.sid === sid && prev.count === sig.count && prev.tail === sig.tail) {
        return  // 指纹一致：无新增
      }
      pollMsgSigRef.current = sig
      if (history.length > local.length) {
        // 对端追加：按 msg_id 全量去重合入（2026-11-18 修复「整段对话重复 12 遍」：
        // 此前按条数切片 history.slice(local.length)——库里一旦存在重复副本，
        // 全部副本被当新消息合入本地，下一轮保存又整段重插，副本指数放大）；
        // 旧数据无 id 时退回按「角色+内容」去重（内容级误杀概率低，可接受）
        const localIds = new Set(local.map((m) => m.msg_id).filter(Boolean))
        const localSig = new Set(local.map((m) => `${m.role}|${(m.content || '').slice(0, 200)}`))
        const fresh = parseHistory(history).filter((m) =>
          m.msg_id ? !localIds.has(m.msg_id)
            : !localSig.has(`${m.role}|${(m.content || '').slice(0, 200)}`))
        if (fresh.length) {
          setMessages([...local, ...fresh])
          setAutoReadTick((t) => t + 1)  // 自动朗读联动（新消息到达即播）
        }
      }
    } catch { /* 静默：同步失败下轮再试 */ }
  }, [])
  useEffect(() => {
    const onFocus = () => { syncPoll() }
    const onVis = () => { if (!document.hidden) syncPoll() }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVis)
    const t = setInterval(syncPoll, 15000)
    return () => {
      clearInterval(t)
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [syncPoll])
  // Claude Code 桥接待审批命令
  const [pendingApproval, setPendingApproval] = useState<{ decision_id: string; tool_name: string; command: string; claude: boolean } | null>(null)
  // 消息点赞（下标 → 已赞）与修改编辑态（消息下标，null = 非编辑态）
  // #30：反馈键=msg_id（字符串）或下标回退——统一 string 键
const [feedback, setFeedbackState] = useState<Record<string, { liked: boolean; disliked: boolean }>>({})
  // 自动朗读（默认开启，与顶部栏喇叭/设置页开关共享 useAutoRead 同步）
  const autoRead = useAutoRead()
  // 多端同步 P1（2026-11-09）：偏好上云——挂载拉服务端覆盖本地，之后变更回写。
  // prefsReadyRef 防默认值在服务端偏好到达前把服务端冲掉
  const prefsReadyRef = useRef(false)
  useEffect(() => {
    (async () => {
      const prefs = await fetchUserPrefs()
      if (prefs.entertainmentMode === '0' || prefs.entertainmentMode === '1') {
        setEntMode(prefs.entertainmentMode === '1')
        try { localStorage.setItem('entertainmentMode', prefs.entertainmentMode) } catch { /* 忽略 */ }
      }
      if (prefs.chatBackend === 'auto' || prefs.chatBackend === 'cloud' || prefs.chatBackend === 'local') {
        setChatBackend(prefs.chatBackend)
      }
      if (prefs.autoRead === '0' || prefs.autoRead === '1') {
        setAutoReadValue(prefs.autoRead === '1')
      }
      // @ 粘性定向已退役（多窗口 v2，2026-11-13）：只回填执行窗口定向映射
      const server = prefs.dmTargets
      if (server && typeof server === 'object' && !Array.isArray(server)) {
        setDmTargets((prev) => {
          const next = { ...prev, ...server }  // 服务端条目覆盖本地同名会话
          try { localStorage.setItem('dmTargets', JSON.stringify(next)) } catch { /* 忽略 */ }
          return next
        })
      }
      prefsReadyRef.current = true
    })()
    // 仅挂载执行一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // 变更回写（fire-and-forget；prefsReady 之后才写）
  useEffect(() => { if (prefsReadyRef.current) putUserPrefs({ entertainmentMode: entMode ? '1' : '0' }) }, [entMode])
  useEffect(() => { if (prefsReadyRef.current) putUserPrefs({ chatBackend }) }, [chatBackend])
  useEffect(() => { if (prefsReadyRef.current) putUserPrefs({ autoRead: autoRead ? '1' : '0' }) }, [autoRead])
  useEffect(() => { if (prefsReadyRef.current) putUserPrefs({ dmTargets }) }, [dmTargets])
  // 回答完成提示音（U5，默认开启，设置页可关）
  const answerTone = useAnswerTone()
  // 模型自主界面联动（2026-10-22）：set_theme 工具 → 后端 theme_event → 主题切换
  const { setTheme: applyTheme } = useTheme()
  const [autoReadTick, setAutoReadTick] = useState(0)
  const feedbackPendingRef = useRef<Set<string>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  // 发送计数：每次发送/修改重发 +1，ChatView 据此无条件滚底并恢复跟随
  const [sendTick, setSendTick] = useState(0)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const sidRef = useRef(currentSid)
  sidRef.current = currentSid
  const loadingRef = useRef(loading)
  loadingRef.current = loading
  // U5 回答完成提示音：生成结束（loading 翻转）且有实际回答内容时响一声
  const prevLoadingRef = useRef(loading)
  useEffect(() => {
    const wasLoading = prevLoadingRef.current
    prevLoadingRef.current = loading
    if (!wasLoading || loading || !answerTone) return
    const last = messagesRef.current[messagesRef.current.length - 1]
    if (last && last.role === 'assistant' && last.content) playAnswerTone()
  }, [loading, answerTone])
  // 在途流（P1-1 停止生成/会话切换守卫）：sid + AbortController
  const streamRef = useRef<{ sid: string; controller: AbortController } | null>(null)
  // 思考时长计时起点（2026-11-06）：发送时刻 → 首个回答 token 的间隔 =
  // 模型思考+工具执行时长，消息脚注展示（Claude Code 风格）
  const thinkingStartRef = useRef(0)
  // 会话加载序号（2026-10-19）：快速切换会话时丢弃迟到响应
  const loadSeqRef = useRef(0)
  // 轻提示（handleSend 静默 return 反馈，2s 自动消失）
  const [notice, setNotice] = useState('')
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flashNotice = (text: string) => {
    setNotice(text)
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current)
    noticeTimerRef.current = setTimeout(() => setNotice(''), 2000)
  }
  // 停止生成：abort → 补「已停止」标记 → 立即落库（abort 后 onDone/onError 不触发）
  const stopStream = () => {
    const s = streamRef.current
    if (!s) return
    streamRef.current = null
    try { s.controller.abort() } catch { /* 忽略 */ }
    // 2026-10-19 修复：此前 setMessages 后用 messagesRef 落库——ref 仍是旧快照，
    // stopped 标记从未持久化。先算好数组同时用于渲染与保存。
    const stoppedMsgs = (() => {
      const last = [...messagesRef.current]
      const i = last.length - 1
      if (i >= 0) last[i] = { ...last[i], stopped: true }
      return last
    })()
    setMessages(stoppedMsgs)
    setLoading(false)
    // 立即保存已生成内容（encodeMsg 会带上 stopped 短键）；
    // 审查修复：与 onDone 同口径走委派双写（停止后执行日志同样落执行窗口）
    const finalMsgs = flushVoiceTranscripts(stoppedMsgs)
    void (async () => {
      const { decoded, split } = await persistSession(finalMsgs, s.sid)
      if (split && sidRef.current === s.sid) {
        const cur = messagesRef.current
        const tailSame = cur.length === finalMsgs.length
          && cur.every((m, i) => m === finalMsgs[i])
        if (tailSame) {
          messagesRef.current = decoded
          setMessages(decoded)
          setFeedbackState((p) => remapFeedback(p, cur, decoded))
        }
      }
      refreshSessions()
      window.dispatchEvent(new Event('yuan-ctx-refresh'))  // 上下文用量徽标即时刷新
    })()
  }
  // 会话切换/新建/删除守卫：流式进行中先停并保存
  const guardBusySession = (): boolean => {
    if (!loading || !streamRef.current) return true
    if (!window.confirm('回复仍在生成，切换将停止并保存已生成内容，继续？')) return false
    stopStream()
    return true
  }

  // 子页面浮窗/浮层宿主（统一入口形态 2026-10-17）：用户手动开/关，AI 不自动开关
  // 形态：桌面=对话内可拖动+可缩放浮窗 / 移动=对话内全屏浮层（都不离开对话）
  const [panel, setPanel] = useState<{ path: string; title: string } | null>(null)
  const handleOpenPanel = useCallback((link: string) => {
    const resolved = resolvePanel(link)
    setPanel({ path: link, title: resolved?.title || '面板' })
  }, [])
  // 桌面浮窗位置/尺寸（可拖动 + 右下角可随意放大缩小；null = 默认）
  const [planPos, setPlanPos] = useState<{ x: number; y: number } | null>(null)
  const [planSize, setPlanSize] = useState<{ w: number; h: number } | null>(null)
  const planDragRef = useRef<{ startX: number; startY: number; baseX: number; baseY: number } | null>(null)
  const planResizeRef = useRef<{ startX: number; startY: number; baseW: number; baseH: number } | null>(null)

  // 后台执行中的计划（指示条数据源；15s 轮询，有 queued/running 才显示）
  const [activePlans, setActivePlans] = useState<{ id: number; title: string; status: string; progress: number; done_steps: number; total_steps: number }[]>([])
  useEffect(() => {
    const poll = async () => {
      try {
        const { listPlans } = await import('../api/plan')
        const all = await listPlans()
        setActivePlans(all.filter((p) => p.status === 'queued' || p.status === 'running')
          .slice(0, 3).map((p) => ({ id: p.id, title: p.title, status: p.status,
                                     progress: p.progress, done_steps: p.done_steps, total_steps: p.total_steps })))
      } catch { /* 静默 */ }
    }
    poll()
    const t = setInterval(poll, 15000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth <= 768
      setIsMobile(mobile)
      if (mobile) setSidebarOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // 轮询 Agent 在线状态（本地统筹 + Claude 桥接），供模式选择器置灰/点亮
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/agent-status`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        })
        if (!res.ok) return
        const data = await res.json()
        if (Array.isArray(data)) {
          const hasLocal = data.some((a: any) => !(a.capabilities || []).includes('claude_code'))
          const hasBridge = data.some((a: any) => (a.capabilities || []).includes('claude_code'))
          setLocalOnline(hasLocal)
          // 本机 Agent 是二合一进程（统筹 + Claude 分支），在线即可用 ⌘ 模式；
          // 独立桥接进程在线时同样点亮
          setClaudeOnline(hasBridge || hasLocal)
          setStatusKnown(true)
        }
      } catch { /* 忽略轮询失败，保持上次状态 */ }
    }
    poll()
    const interval = setInterval(poll, 10000)
    return () => clearInterval(interval)
  }, [])

  // 当前模式对应的 Agent 掉线时自动回落到云端（首次轮询完成前不判定）
  useEffect(() => {
    if (!statusKnown) return
    if (chatMode === 'local' && !localOnline) setChatMode('cloud')
  }, [chatMode, localOnline, claudeOnline, statusKnown])

  const refreshSessions = useCallback(async () => {
    // 多窗口 P1：只拉当前窗口的会话列表——chat 也显式过滤（审查修复：
    // 空参数后端语义是「不过滤」，执行窗口会话会混进主对话侧栏）。
    // sweep 审查修复：迟到响应守卫——窗口已切换后，旧窗口的列表不得落地
    const kind = agentKindRef.current
    const list = await listSessions(kind)
    if (agentKindRef.current === kind) setSessions(list)
    return list
  }, [])

  // 会话切换/挂载后滚到最新消息：历史是异步加载的（loadMessages await 后 setMessages），
  // 只靠 ChatView 的 currentSid 变化判定会在历史到达前滚旧内容——这里在历史渲染后
  // 用 rAF 补一次强制滚底（时序缺口修复，配合 ChatView 的 sessionChanged 滚动）
  const scrollToLatest = () => {
    requestAnimationFrame(() => {
      const el = document.querySelector('.chat-main')
      if (el) el.scrollTop = el.scrollHeight
    })
  }

  // 挂载时确保置顶主对话存在（豆包式：每用户一条，取/建幂等）并直接落主对话——
  // 登录即进主对话，欢迎页仅在接口异常时作兜底
  useEffect(() => {
    const init = async () => {
      try {
        const main = await ensureMainSession()
        await refreshSessions()
        if (main && !sidRef.current) {
          setCurrentSid(main.session_id)
          const historyResp = await loadMessages(main.session_id)
          if (historyResp == null) { setLoadFailed(true); return }  // 同上：失败态阻断发送
          setLoadFailed(false)
          setMessages(historyResp.length === 0
            ? []  // 空对话不再塞问候语（2026-10-31 用户拍板）：显示主页 logo 吉祥物 + 推荐问题
            : parseHistory(historyResp))
          scrollToLatest()
        }
      } catch {
        setInitFailed(true)  // 接口异常：重试框（不再闪欢迎页）
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshSessions])

  // 语音聊天状态机（会话锚定/转录队列/保存快照 flush，独立 hook）
  const {
    voiceCallOpen, setVoiceCallOpen,
    ensureVoiceSession, startVoiceCall,
    handleVoiceTranscript, flushVoiceTranscripts,
  } = useVoiceCall({
    sidRef, messagesRef, loadingRef,
    setMessages, setCurrentSid,
    // 多窗口 P1：refreshSessions 返回会话列表供切换器用；voice hook 只关心刷新副作用
    refreshSessions: () => refreshSessions().then(() => undefined),
  })

  // 麦克风权限必须在点击手势内同步申请：Chrome 的用户激活（约 5s）过期后
  // getUserMedia 会被静默拒绝（NotAllowedError），连询问框都不弹。
  // 先申请拿权限即释放，SDK 进房后重新采集时权限已在，不会再弹框。
  // 单点实现：输入区/欢迎页两个话筒按钮共用，不再各自拷贝。
  const startVoiceCallWithPermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((t) => t.stop())
      startVoiceCall()
    } catch {
      alert('麦克风权限被拒绝：请点击浏览器地址栏左侧图标，将麦克风设为「允许」后重试')
    }
  }

  const handleNewSession = async () => {
    if (!guardBusySession()) return
    // 新建当前窗口的会话并立即打开（登录已直接落主对话，新对话按钮=另开一个会话）
    const kind = agentKindRef.current
    const cfg = AGENT_CONFIG[kind === 'chat' ? 'orchestrator' : kind]
    const sid = await createSession(kind === 'chat' ? undefined : cfg.label, kind === 'chat' ? undefined : kind)
    if (kind !== 'chat') {
      saveDmTarget(sid, kind)
      setTargetAgent(kind)
    }
    saveLastSid(kind, sid)
    setCurrentSid(sid)
    setMessages(kind === 'chat' ? [] : [{ role: 'assistant', content: `已打开「${cfg.label}」独立窗口：本窗口内的消息都将直接交给${cfg.label}处理，执行过程与结果不占用主对话历史。`, sender: kind as any, toolCalls: [] }])
    setInput('')
    setImages([])
    setFeedbackState({})
    setEditingIndex(null)
    refreshSessions()
  }

  // 打开一个会话（切换器/会话列表/新建共用）：加载消息与点赞态
  const openSession = async (sid: string) => {
    setCurrentSid(sid)
    // 2026-10-19 修复①：切换会话清掉上一会话的审批卡——残留时点「同意」会把
    // 决议发给新会话（错会话审批）
    setPendingApproval(null)
    // 旧小窗会话（@私聊）：恢复持久定向；无定向的会话清空 stale 定向（审查修复：
    // 此前打开无 dm 的会话不清 targetAgent，前一个窗口的定向静默泄漏到主对话）
    const dm = dmTargetsRef.current[sid]
    setTargetAgent(dm || '')
    // 2026-10-19 修复②：请求序号守卫——快速 A→B 切换时先发的 loadMessages(A)/
    // loadFeedback(A) 可后到并覆盖 B 的消息与点赞态；两请求并行（审查效率修复）
    const seq = ++loadSeqRef.current
    const [historyResp, feedbackData] = await Promise.all([loadMessages(sid), loadFeedback(sid)])
    if (seq !== loadSeqRef.current) return  // 已切到别的会话：丢弃迟到响应
    // sweep 审查修复：加载失败与「空会话」必须区分——按空会话展示会让用户
    // 直接发送，/chat/save 全量替换把既有历史清空；失败态阻断发送
    if (historyResp == null) { setLoadFailed(true); return }
    setLoadFailed(false)
    const history = historyResp
    setFeedbackState(feedbackData)
    setEditingIndex(null)
    setMessages(history.length === 0
      ? []  // 空对话显示吉祥物 logo（2026-10-31）
      : parseHistory(history))
    // 多端同步：以刚加载的历史为指纹基线，首个轮询周期直接比对增量
    pollMsgSigRef.current = {
      sid, count: history.length,
      tail: String(history[history.length - 1]?.content || ''),
    }
    scrollToLatest()  // 历史异步加载完成后补滚（时序缺口）
    if (isMobile) setSidebarOpen(false)  // P2：移动端选中会话后收起侧栏
  }

  const handleSelectSession = async (sid: string) => {
    if (sid === currentSid) return
    if (!guardBusySession()) return
    saveLastSid(agentKindRef.current, sid)
    await openSession(sid)
  }

  // 切换智能体窗口（侧边栏切换器 / 任务卡「去执行窗口」）：会话列表换成该智能体的；
  // 优先回到该窗口上次打开的会话；任务卡跳转传 sidOverride 精确定位执行会话；
  // 该智能体还没有会话则自动新建（豆包式点智能体即有对话）。
  // 返回是否切换成功（toggleEntMode 需要——guard 取消时防「半切换」）
  const switchSeqRef = useRef(0)
  const handleSwitchKind = async (kind: 'chat' | 'claude' | 'automation', sidOverride?: string): Promise<boolean> => {
    if (kind === agentKindRef.current && !sidOverride) return true
    // sweep 审查修复：娱乐模式不进入执行窗口——切换器/模式菜单在娱乐下隐藏，
    // 进窗后无出口（历史任务卡/指示条 chip 仍可触发），困住用户
    if (entMode && kind !== 'chat') return false
    if (!guardBusySession()) return false
    // 审查修复①：全链序号守卫——快速连点不同智能体时，先发出的 listSessions
    // 迟到不得覆盖新窗口的列表/会话
    const seq = ++switchSeqRef.current
    setAgentKind(kind)
    setTargetAgent('')  // 切窗清定向（openSession 按 dmTargets 恢复）
    const list = await listSessions(kind)  // 显式 kind 过滤（chat 窗口不混入执行会话）
    if (seq !== switchSeqRef.current) return false
    setSessions(list)
    let sid = ''
    if (sidOverride && list.some((s) => s.session_id === sidOverride)) sid = sidOverride
    if (!sid) sid = lastSidByKindRef.current[kind]
    if (!sid || !list.some((s) => s.session_id === sid)) sid = list[0]?.session_id || ''
    let created = false
    if (!sid) {
      // 审查修复②：AGENT_CONFIG 无 'chat' 键（chat 会话列表为空几乎不可能——
      // 主对话是锚点，但断网时 listSessions 静默返回 []，防御）
      const cfg = kind === 'chat' ? AGENT_CONFIG.orchestrator : AGENT_CONFIG[kind]
      sid = await createSession(cfg.label, kind)
      if (seq !== switchSeqRef.current) return false
      if (kind !== 'chat') saveDmTarget(sid, kind)
      created = true
      await refreshSessions()  // 重拉列表（补 agent_kind/真实时间；seq 守卫在上方）
      if (seq !== switchSeqRef.current) return false
    }
    saveLastSid(kind, sid)
    await openSession(sid)
    if (seq !== switchSeqRef.current) return false
    if (kind !== 'chat') setTargetAgent(kind)  // 执行窗口固定定向该智能体
    if (created) {
      const cfg = kind === 'chat' ? AGENT_CONFIG.orchestrator : AGENT_CONFIG[kind]
      setMessages([{ role: 'assistant', content: `已打开「${cfg.label}」独立窗口：本窗口内的消息都将直接交给${cfg.label}处理，执行过程与结果不占用主对话历史。`, sender: kind as any, toolCalls: [] }])
    }
    return true
  }

  // U2 会话重命名（2026-10-25）：prompt 输入新标题 → 后端归属校验更新 →
  // 刷新列表；改名后 /chat/save 的自动标题不会覆盖（_is_auto_title 不命中）
  // 会话昵称：首轮对话结束后 AI 自动生成（/chat/save fire-and-forget；
  // 2026-11-06 用户拍板去掉侧栏手动星光按钮）

  // V1-4 分享（2026-11-06）：生成公开链接并复制；已分享则重新生成（幂等覆盖）
  const handleShareSession = async (sid: string) => {
    try {
      const { url } = await shareSession(sid)
      const full = window.location.origin + url
      try { await navigator.clipboard.writeText(full) } catch { /* 忽略 */ }
      window.alert(`分享链接已生成并复制：
${full}

任何访客均可查看（含 AI 生成标识）。取消分享可再次点击分享按钮。`)
    } catch (e: any) {
      window.alert(e.message || '分享失败，请重试')
    }
  }

  const handleRenameSession = async (sid: string, oldTitle: string) => {
    const title = window.prompt('新标题', oldTitle)
    if (!title || !title.trim() || title.trim() === oldTitle) return
    const ok = await renameSession(sid, title.trim())
    if (ok) refreshSessions()
    else window.alert('重命名失败，请重试')
  }

  // ---- 回收站（2026-10-30 软删除）：列表/恢复/彻底删除 ----
  const [trashOpen, setTrashOpen] = useState(false)
  const [trashList, setTrashList] = useState<any[]>([])
  const [trashBusy, setTrashBusy] = useState(false)

  const loadTrash = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/trash`, { headers: authHeaders() })
      if (res.ok) setTrashList(await res.json())
    } catch { /* 忽略 */ }
  }
  const openTrash = () => { setTrashOpen(true); loadTrash() }
  const handleRestoreSession = async (sid: string) => {
    setTrashBusy(true)
    await fetch(`${API_BASE}/chat/trash/${sid}/restore`, { method: 'POST', headers: authHeaders() })
    setTrashBusy(false)
    refreshSessions()
    loadTrash()
  }
  const handlePurgeSession = async (sid: string) => {
    if (!window.confirm('彻底删除该会话？历史消息将无法恢复。')) return
    setTrashBusy(true)
    await fetch(`${API_BASE}/chat/trash/${sid}`, { method: 'DELETE', headers: authHeaders() })
    setTrashBusy(false)
    refreshSessions()
    loadTrash()
  }

  // 主对话降级为普通对话（2026-10-30）：不清数据——自动新建空主对话并切过去
  const handleDemoteMain = async (sid: string) => {
    if (!window.confirm('将主对话转为普通对话？全部历史会保留在本对话中，并自动新建一条空主对话。')) return
    if (loading && streamRef.current && sidRef.current === sid) stopStream()
    try {
      const res = await fetch(`${API_BASE}/chat/demote-main`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ session_id: sid }),
      })
      const data = await res.json()
      if (!res.ok || !data.new_session_id) { flashNotice(data?.detail || '操作失败'); return }
      refreshSessions()
      setCurrentSid(data.new_session_id)
      setMessages([])
      flashNotice('已转为普通对话，新主对话已创建')
    } catch { flashNotice('操作失败，请重试') }
  }

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    const title = sessions.find((s) => s.session_id === sid)?.title || '该会话'
    if (!window.confirm(`删除会话「${title}」？该操作不可恢复。`)) return
    if (loading && streamRef.current && sidRef.current === sid) stopStream()
    await deleteSession(sid)
    flashNotice('已移入回收站（可在侧栏回收站恢复）')
    if (currentSid === sid) { setCurrentSid(''); setMessages([]) }
    // 清理小窗定向映射孤儿（删除会话后 localStorage 里残留的 dmTargets 键）
    setDmTargets((prev) => {
      if (!(sid in prev)) return prev
      const next = { ...prev }
      delete next[sid]
      try { localStorage.setItem("dmTargets", JSON.stringify(next)) } catch { /* 存储受限，仅本次会话 */ }
      return next
    })
    refreshSessions()
  }

  const SYSTEM_PROMPT_BASE = '你是小元AI的统筹助手。数据分析、数据采集、生命科学等能力以「脚本工具」（script_ 开头）直接挂在你名下，一次函数调用即可选定脚本并执行，不需要委派。\n\n## 工具\n- 脚本工具：script_descriptive_stats（描述性统计）/ script_correlation（相关性）/ script_regression（回归）/ script_categorical（分类数据）/ script_timeseries（时间序列）/ script_preprocess（数据预处理）/ script_rfm_cluster（RFM 分群）/ script_churn_predict（流失预测）/ script_gene_expression（基因表达）/ script_generic_crawl（通用网页采集）\n- create_plan：多步组合任务先拆草稿计划（每步写清 skill 与意图，能确定脚本时填 script 工具名与 params，信息不足先问用户）；execute_plan：用户说「执行」时把计划加入队列；get_plan_status：查询进度\n- search_web：联网搜索（query 核心短语分词；摘要通常已足够回答，仅需正文详情时才用 fetch_url + parse_html）\n- retrieve_planet_knowledge：检索用户个人知识星球（导图/笔记，只读）\n- delegate_to_automation_agent：仅浏览器控制/审核等需多步自主操作的任务\n\n## 计划流\n多步骤组合任务（如「先抓取数据，再做统计分析」）先用 create_plan 制定草稿计划并向用户复述步骤，说明「说『执行』才会开始」；用户明确说执行时再调用 execute_plan。不要用文字代替计划、不要连续自行委派执行。\n\n## 群聊说话人协议\n历史消息中带【xx Agent】前缀的是其他智能体说过的话，不是你说的；无前缀的 assistant 消息才是你自己说过的。不要复述、冒充或接续别人的话，不要替其他智能体总结其发言。\n\n## 工作原则\n1. 判断意图：分析/采集类直接选脚本工具执行，一句话说明在做什么\n2. 工具返回结果清晰完整时，只做简短确认如“以上是结果”，不要再复述；需要解读、比较或给出建议时才补充分析\n3. 每段回答的结尾必须使用句号等完整标点收尾，不要戛然而止（用户会误以为回复被截断）\n4. 对话结束或任务完成时，用自然语言简短总结本次完成了什么、关键结论是什么（几句话要点即可）\n5. 表达风格用户友好：技术内容多给代码示例；数据对比、统计结果必须用图表直观表达（` ```html` 交互页面 / ` ```svg` 图形 / ` ```mermaid` 图表；脚本工具产出的 plotly 看板客户端自动渲染并附「打开面板」入口）——不要输出 markdown 表格堆数字\n6. 写 HTML 页面时，页面底部必须带小元AI 入口条：固定底栏、品牌蓝渐变底白字（linear-gradient(135deg,#3b82f6,#2563eb)）、文案「由 小元AI 生成 · 打开官网」链接 https://cjyuanai.cn（target=_blank）、页面内容底部留 44px 空间'

  // 助手设定（2026-10-17）：后台设定中心可覆盖聊天提示词（chat_system_prompt
  // + capability_note）；拉取失败回退内置常量
  const [sysPrompt, setSysPrompt] = useState(SYSTEM_PROMPT_BASE)
  useEffect(() => {
    fetch(`${API_BASE}/chat/system-prompt`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.system_prompt) return
        let p = d.system_prompt
        if (d.capability_note) p += '\n\n' + d.capability_note
        setSysPrompt(p)
      })
      .catch(() => {})
  }, [])

  const makeStreamHandlers = (noOrchestratorReset = false) => {
    // 本地 Agent 模式气泡显示「小元AI · 本机」，云端模式显示「小元AI」，Claude 模式显示 Claude Code
    // noOrchestratorReset：claude 流/定向小窗里没有统筹参与，工具结束不得复位成统筹气泡
    //（否则 Claude 工具后 token 落进新开的统筹气泡 → CC 与小元交替、最终答案归小元）
    let currentSender = chatMode === 'cloud' ? 'orchestrator' : 'local'
    const onEvent = (event: any) => {
      // 旁路守卫（P1-1）：流式期间会话已切换/停止 → 丢弃迟到事件，防跨会话写入
      const s = streamRef.current
      if (!s || s.sid !== sidRef.current) return
      if (event.type === 'backend_event') {
        // N3：模型/用户命令切换执行后端 → 分段开关跟随
        const b = event.data?.backend
        if (b === 'auto' || b === 'cloud' || b === 'local') setChatBackend(b)
      } else if (event.type === 'mode_event') {
        // 模式自主路由（2026-10-22）：后端模型判定切换娱乐/工作 → 分段开关跟随
        const m = event.data?.mode
        if (m === 'entertainment' || m === 'work') {
          const next = m === 'entertainment'
          setEntMode(next)
          try { localStorage.setItem('entertainmentMode', next ? '1' : '0') } catch { /* 忽略 */ }
          if (next) {
            prevChatModeRef.current = chatMode
            setChatMode('cloud')
            setTargetAgent('')
          } else {
            setChatMode(prevChatModeRef.current || 'local')
          }
        }
        return
      }
      if (event.type === 'theme_event') {
        // set_theme 工具 → 模型自主切换明暗主题（ThemeContext 负责 DOM/localStorage/服务端）
        const t = event.data?.theme
        if (t === 'dark' || t === 'light') applyTheme(t)
        return
      }
      if (event.type === 'compliance_warning') {
        // C6 输出侧审核（2026-10-29）：回复命中内容审核 → 气泡挂常驻警告条（人工复核中）
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], complianceWarning: true }; return last })
        return
      }
      if (event.type === 'suggestions') {
        // 追问预测（2026-10-31）：AI 预测用户接下来可能问的问题 → 挂气泡下可点追问
        const items = (event.data?.items || []).filter((x: any) => typeof x === 'string').slice(0, 3)
        if (items.length) {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], suggestions: items }; return last })
        }
        return
      }
      if (event.type === 'usage_event') {
        // 本次 token 消耗（2026-11-06）：后端 done 前发——挂当前气泡脚注
        //（思考时长 · 消耗 N tokens · ≈¥成本）；桥接路径无此事件则不显示
        const u = event.data || {}
        if (u.prompt_tokens || u.completion_tokens) {
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], usage: { prompt_tokens: u.prompt_tokens || 0, completion_tokens: u.completion_tokens || 0, cache_hit_tokens: u.cache_hit_tokens || 0, cost: u.cost, model: u.model } }; return last })
        }
        return
      }
      if (event.type === 'token') {
        // 时序交叉渲染：首个 token 时把累积思考快照为「最终思考」（回答前展示），
        // 之后 reasoning 字段复位（下一阶段重新累积）。
        // 2026-11-06：首个 token 同时结算思考时长（发送 → 首 token 间隔）
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const firstToken = !last[i].content && !last[i].finalReasoning; const reasoningTime = firstToken && last[i].reasoningTime === undefined && thinkingStartRef.current ? Math.max(1, Math.round((Date.now() - thinkingStartRef.current) / 1000)) : undefined; last[i] = { ...last[i], content: last[i].content + event.data, sender: (last[i].sender || currentSender) as any, ...(reasoningTime ? { reasoningTime } : {}), ...(firstToken && last[i].reasoning ? { finalReasoning: last[i].reasoning, reasoning: '' } : {}) } }; return last })
      } else if (event.type === 'reasoning') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], reasoning: (last[i].reasoning || '') + event.data }; return last })
      } else if (event.type === 'tool_start') {
        // 信封协议：工具名推断（planet/委托/计划）优先，后端事件 sender 兜底；
        // 统筹自身的工具不开新气泡（toolCalls 挂当前气泡）。
        // 注意：LangGraph v2 事件流对同一次工具调用可能发两轮 start/end——
        // 同一 Agent 连续工具调用必须复用气泡，否则一串空泡（曾出现 5 泡 2 空）
        const evSender = event.data.sender || ''
        const ns = senderFromTool(event.data.name)
          || ((evSender && evSender !== 'orchestrator' && evSender !== 'local') ? evSender : '')
        if (ns) {
          currentSender = ns
          const link = ns === 'automation' ? '/chat/agent/' + ns : ns === 'planet' ? '/chat/planet' : ns === 'plan' ? '/chat/plan' : undefined
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            // 时序交叉：累积思考快照进本次调用卡，原气泡 reasoning 复位重计
            const take = last?.reasoning || ''
            const newCall = { name: event.data.name, status: 'running' as const, ...(take ? { reasoning: take } : {}), ...(event.data.args ? { args: event.data.args } : {}) }
            if (last && last.role === 'assistant' && last.sender === ns && !last.content) {
              // 同一 Agent 连续工具调用/重复事件 → 复用气泡
              const calls = [...(last.toolCalls || [])]
              if (!calls.some((c) => c.name === event.data.name && c.status === 'running')) {
                calls.push(newCall)
              }
              return [...prev.slice(0, -1), { ...last, toolCalls: calls, reasoning: '', pageLink: link || last.pageLink }]
            }
            return [...prev.slice(0, -1), ...(last ? [{ ...last, reasoning: '' }] : []),
              { role: 'assistant' as const, content: '', sender: ns as any, pageLink: link, toolCalls: [newCall] }]
          })
        }
        else {
          // 统筹自身工具（含计划工具）：工具卡挂当前气泡；计划工具同时挂
          // 「打开面板」链接（计划工具不独立成泡后，这是 /chat/plan 的入口）
          const isPlanTool = event.data.name === 'create_plan'
            || event.data.name === 'execute_plan' || event.data.name === 'get_plan_status'
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; const take = last[i].reasoning || ''; calls.push({ name: event.data.name, status: 'running', ...(take ? { reasoning: take } : {}), ...(event.data.args ? { args: event.data.args } : {}) }); last[i] = { ...last[i], toolCalls: [...calls], reasoning: '', pageLink: isPlanTool ? '/chat/plan' : last[i].pageLink } }; return last })
        }
      } else if (event.type === 'dashboard') {
        // 分析大屏数据就绪：给最近的统筹气泡挂「打开面板」（融合后脚本工具
        // 在统筹气泡内执行，不再有 analysis 气泡；兼容历史 analysis 气泡兜底）
        const dsid = event.data?.session_id || sidRef.current
        // A 看板缓存：dashboard_html 存在 → 打开自包含看板轻量页；否则通用大屏
        const boardKey = event.data?.dashboard_html
          ? String(event.data.dashboard_html).split('/').pop() : ''
        setMessages((prev) => {
          const last = [...prev]
          for (let i = last.length - 1; i >= 0; i--) {
            const s = last[i].sender
            if (s === 'orchestrator' || s === 'local' || s === 'analysis') {
              last[i] = { ...last[i], pageLink: boardKey ? '/chat/agent/board/' + boardKey : '/chat/agent/dashboard/' + dsid }
              break
            }
          }
          return last
        })
      } else if (event.type === 'tool_end') {
        const del_name = event.data.name || ''
        // 子 Agent/知识星球工具结束 → 复位统筹并另起气泡；统筹自身工具不另起。
        // 重复 tool_end 事件（LangGraph 双发）会叠空泡——已有空占位泡时不叠加
        const evSender = event.data.sender || ''
        const isDel = !!senderFromTool(del_name)
          || (evSender !== '' && evSender !== 'orchestrator' && evSender !== 'local')
        setMessages(function (prev) {
          const last = prev.slice()
          const i = last.length - 1
          if (i >= 0) {
            // 2026-11-17 修复：按工具名整组覆盖 → 只更新第一条「运行中」的同名调用——
            // CC 一轮 16 次 Bash 时，每次 tool_end 把全部 Bash 结果都覆盖成同一个值
            // （库里 16 条结果全是最后一条清理命令的输出）；SDK loop 顺序执行，
            // 任意时刻至多一条同名调用在运行中，first-running 匹配即精确对应
            const calls = (last[i].toolCalls || []).slice()
            let hit = false
            for (let k = 0; k < calls.length; k++) {
              const c = calls[k]
              if (!hit && c.name === del_name && c.status === 'running') {
                hit = true
                calls[k] = { ...c, status: event.data.is_error ? 'error' : 'done', result: event.data.output || '', ...(event.data.args ? { args: event.data.args } : {}) }
              }
            }
            last[i] = { ...last[i], toolCalls: calls }
          }
          return last
        })
        if (isDel && !noOrchestratorReset) {
          currentSender = 'orchestrator'
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'assistant' && last.sender === 'orchestrator'
                && !last.content && !(last.toolCalls?.length)) {
              return prev  // 已有空的统筹占位泡（上一轮 tool_end 建过）→ 不叠加
            }
            return [...prev, { role: 'assistant' as const, content: '', sender: 'orchestrator', toolCalls: [] }]
          })
        }
      } else if (event.type === 'image') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].images = [...(last[i].images || []), event.data] }; return last })
      } else if (event.type === 'html') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { last[i].htmls = [...(last[i].htmls || []), event.data.url] }; return last })
      } else if (event.type === 'progress') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0 && last[i].role === 'assistant') last[i] = { ...last[i], progress: event.data }; return last })
      } else if (event.type === 'agent') {
        // Claude 桥接声明身份：后续 token 归属该 Agent 气泡（复用尾部空占位气泡，不新增）
        const ns = event.data.sender
        if (ns && AGENT_CONFIG[ns]) {
          currentSender = ns
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'assistant' && !last.content && !(last.toolCalls?.length)) {
              return [...prev.slice(0, -1), { ...last, sender: ns as any }]
            }
            return [...prev, { role: 'assistant' as const, content: '', sender: ns as any, toolCalls: [] }]
          })
        }
      } else if (event.type === 'approval') {
        // source=cloud → 云端直连审批（决议回 /chat/stream）；否则 Claude 桥接审批
        // （决议回 /chat/claude-stream，沿用既有链路）
        setPendingApproval({ decision_id: event.data.decision_id, tool_name: event.data.tool_name, command: event.data.command, claude: event.data.source !== 'cloud' })
      } else if (event.type === 'truncated') {
        // U4 继续生成（2026-10-25）：回答撞 max_tokens 被截断——标记气泡显示「继续生成」
        setMessages((prev) => {
          const last = [...prev]
          const i = last.length - 1
          if (i >= 0) last[i] = { ...last[i], truncated: true }
          return last
        })
      } else if (event.type === 'error') {
        // 展示真实错误信息（截断），便于排查；error 标记进消息（可落库、气泡显示错误卡）；
        // 2026-10-26 截断续写：已有部分回答时挂「继续生成」按钮而不是错误卡
        const errMsg = typeof event.data === 'string' && event.data ? event.data.slice(0, 300) : '请求失败，请重试'
        setMessages((prev) => {
          const last = [...prev]
          const i = last.length - 1
          if (i >= 0) {
            const hasPartial = !!last[i].content && last[i].role === 'assistant'
            last[i] = { ...last[i], content: last[i].content || `请求失败: ${errMsg}`,
                        error: hasPartial ? undefined : `请求失败: ${errMsg}`,
                        ...(hasPartial ? { truncated: true } : {}) }
          }
          return last
        })
        setLoading(false)
      }
    }
    const onError = (msg?: string) => {
      const errText = msg || '网络异常，请检查连接'
      // 2026-10-19 修复：与 stopStream 同病——setMessages 后读 messagesRef 是旧
      // 快照，error 文案从未持久化；先算好数组再渲染+保存
      const errMsgs = (() => {
        const last = [...messagesRef.current]
        const i = last.length - 1
        if (i >= 0) {
          // 2026-10-26 截断续写：流中断但已有部分回答 → 标 truncated，
          // 气泡出现「继续生成」按钮，用户一键接着写（不再只挂错误卡）
          const hasPartial = !!last[i].content && last[i].role === 'assistant'
          last[i] = { ...last[i], content: last[i].content || errText,
                      error: hasPartial ? undefined : errText,
                      ...(hasPartial ? { truncated: true } : {}) }
        }
        return last
      })()
      // 重新生成失败同样回挂其后消息（数据不丢）
      const s = streamRef.current
      streamRef.current = null
      const restored = s ? restoreAfterRegenerate(errMsgs, s.sid) : errMsgs
      setMessages(restored)
      setLoading(false)
      // P1-1：断流也落库（此前 onError 不保存，刷新后部分输出丢失）；
      // 审查修复：与 onDone 同口径走委派双写（否则执行日志落主对话、失败态丢摘要）
      if (s) {
        const finalMsgs = flushVoiceTranscripts(restored)
        void (async () => {
          const { decoded, split } = await persistSession(finalMsgs, s.sid)
          if (split && sidRef.current === s.sid) {
            const cur = messagesRef.current
            const tailSame = cur.length === finalMsgs.length
              && cur.every((m, i) => m === finalMsgs[i])
            if (tailSame) {
              messagesRef.current = decoded
              setMessages(decoded)
              setFeedbackState((p) => remapFeedback(p, cur, decoded))
            }
          }
          refreshSessions()
          window.dispatchEvent(new Event('yuan-ctx-refresh'))
        })()
      }
    }
    return { onEvent, onError }
  }

  // 多窗口 #16（2026-11-13）：委派块双写——主对话里统筹委派 CC/自动化 的执行段
  // 从主对话落库中剥出，全量落执行窗口会话（切过去可回看完整执行日志）；
  // 主对话只落一条任务卡摘要（带 w/wk 窗口引用），60 条截断不被执行日志吃掉。
  // 任何一步失败都退回全量落主对话（不丢数据）。
  // 返回剥除后的主对话消息（decoded）：调用方用它替换 UI 状态——状态与落库一致，
  // 下一轮保存不会再命中历史委派块（审查修复：此前内存保留 CC 气泡导致每轮重复拆分）。
  const persistSession = async (finalMsgs: ChatMessage[], sid: string, title?: string) => {
    // #30：编辑重发截断的显式删除列表（handleEditMessage 收集，发送即消费）
    const deletedIds = pendingDeletedIdsRef.current.splice(0)
    if (agentKindRef.current !== 'chat') {
      const ok = await saveMessages(sid, finalMsgs.map(encodeMsg), title, deletedIds)
      return { decoded: finalMsgs, split: false, ok }
    }
    // 委派段按发送者分组（审查修复：一轮同时委派 CC+自动化 → 各自落各自窗口）
    const groups: Record<string, ChatMessage[]> = {}
    for (const m of finalMsgs) {
      if (m.role === 'assistant' && (m.sender === 'claude' || m.sender === 'automation')) {
        (groups[m.sender] = groups[m.sender] || []).push(m)
      }
    }
    const kinds = Object.keys(groups) as ('claude' | 'automation')[]
    if (!kinds.length) {
      const ok = await saveMessages(sid, finalMsgs.map(encodeMsg), title, deletedIds)
      return { decoded: finalMsgs, split: false, ok }
    }
    const removed = new Set<ChatMessage>()
    const summaries: ChatMessage[] = []
    let windowAllOk = true
    for (const winKind of kinds) {
      const dlgt = groups[winKind]
      dlgt.forEach((m) => removed.add(m))
      let winSid = ''
      try {
        // 执行窗口会话：上次会话 + 列表校验（sweep 审查修复：已软删的会话
        // loadMessages 返回 200 [] 而非失败，不校验会把日志写进回收站会话）；
        // 无则自动新建并补持久定向（审查修复：此前漏 saveDmTarget，
        // 第二条消息起定向丢失被统筹接管）
        const list = await listSessions(winKind)
        winSid = lastSidByKindRef.current[winKind] || ''
        if (!winSid || !list.some((s) => s.session_id === winSid)) winSid = list[0]?.session_id || ''
        if (!winSid) {
          winSid = await createSession(AGENT_CONFIG[winKind].label, winKind)
          saveDmTarget(winSid, winKind)
        }
        saveLastSid(winKind, winSid)
        // 窗口历史 append（saveMessages 是全量替换语义 → 读旧 + 拼新 = 天然幂等）；
        // 读失败（null）不得当空数组——否则全量替换把窗口历史清空（审查修复）
        const winRows = await loadMessages(winSid)
        if (winRows == null) { windowAllOk = false; break }
        const winMsgs = [...winRows]
        // 指令块：本轮用户原话副本（窗口尾部不是同一指令时追加）
        const userMsg = [...finalMsgs].reverse().find((m) => m.role === 'user')
        const lastRow = winMsgs[winMsgs.length - 1]
        if (userMsg && (lastRow?.role !== 'user' || lastRow.content !== encodeMsg({ ...userMsg }).content)) {
          winMsgs.push(encodeMsg({ ...userMsg, sender: undefined, recipient: undefined }))
        }
        for (const d of dlgt) winMsgs.push(encodeMsg(d))
        // 审查修复：await 且失败可感知（saveMessages 此前吞错，兜底是死代码）
        const ok = await saveMessages(winSid, winMsgs)
        if (!ok) windowAllOk = false
      } catch {
        windowAllOk = false
      }
      // 摘要卡（透传失败/停止状态——审查修复：失败态不得在刷新后丢失）
      const lastD = dlgt[dlgt.length - 1]
      const raw = (lastD.content?.trim() || (lastD.toolCalls || []).slice(-1)[0]?.result?.trim() || '')
      const summary = raw.length > 300 ? raw.slice(0, 300) + '…' : (raw || '（无文本输出，详见执行窗口）')
      summaries.push({
        role: 'assistant', sender: 'orchestrator', msgType: 'note',
        content: `${summary}\n\n— 完整执行过程与结果见 ${AGENT_CONFIG[winKind].label} 窗口`,
        windowSession: winSid, windowKind: winKind,
        ...(lastD.error ? { error: lastD.error } : {}),
        ...(lastD.stopped ? { stopped: true } : {}),
      } as any)
    }
    // 主对话：窗口写全成功 → 剥除委派段 + 摘要；否则全量兜底（不丢数据）
    const decoded = windowAllOk
      ? [...finalMsgs.filter((m) => !removed.has(m)), ...summaries]
      : finalMsgs
    const ok = await saveMessages(sid, decoded.map(encodeMsg), title, deletedIds)
    return { decoded, split: true, ok }
  }

  // 剥离委派段后下标整体前移——feedback 按 message_index 定位，必须同步重映射
  // （审查修复：否则点赞挂到错误气泡；#30 消息 id 落地后按 id 定位可退役）
  const remapFeedback = (prev: Record<number, any>, oldMsgs: ChatMessage[], newMsgs: ChatMessage[]) => {
    const seen = new Map<ChatMessage, number>()
    oldMsgs.forEach((m, i) => { if (!seen.has(m)) seen.set(m, i) })
    const map = new Map<number, number>()
    newMsgs.forEach((m, ni) => { const oi = seen.get(m); if (oi !== undefined) map.set(oi, ni) })
    const next: Record<number, any> = {}
    for (const [k, v] of Object.entries(prev)) {
      const nk = map.get(Number(k))
      if (nk !== undefined) next[nk] = v
    }
    return next
  }

  // 通用发送链路：msgs 为发送时的完整消息数组（不含新的 assistant 占位气泡），
  // 普通发送与「修改后截断重发」共用；sid 在发送时捕获，防止流式期间切换会话写错库。
  // 注意：Claude 桥接模式按 cloud session_id 续接 claude 会话（无法回退），
  // 修改重发等同「继续对话」，模型仍记得修改前的上下文。
  const sendMessages = (msgs: ChatMessage[], prompt: string, sentImages?: string[], title?: string) => {
    const sid = sidRef.current
    setLoading(true)
    // 普通消息自动撤销未决审批（桥接侧会 deny pending 后正常处理）
    setPendingApproval(null)
    // 执行窗口会话（dmTargets）持久定向；主对话走统筹自行路由——
    // @ 面板与粘性定向已退役（多窗口 v2，2026-11-13）。审查修复：执行窗口按
    // 窗口类型兜底定向——自动建窗的会话可能暂无 dmTargets 映射（刚写入 state
    // 未更新 ref 的窗口期），且不再有「单次定向复位」清掉窗口固定定向
    // 娱乐模式（E1）：不委派——忽略窗口定向，纯云端小元AI 回答
    const dmTarget = entMode ? '' : (dmTargetsRef.current[sid] || '')
    const kindTarget = entMode ? '' : (agentKindRef.current !== 'chat' ? agentKindRef.current : '')
    const target = dmTarget || kindTarget || (entMode ? '' : targetAgentRef.current)
    const isClaude = !entMode && (target === 'claude' || chatMode === 'claude')
    // 防重复发送（2026-11-18）：msgs 末条即本轮 prompt，后端还会把 prompt
    // 单独追加为末条 user——同文时从历史剥掉，否则模型把最新问题看两遍
    // （分享会话实测模型自报「本条出现 2 次」）；prompt 的信封（recipient 定向
    // target / turn 计数）由后端按 target 字段构造，此处剥掉不丢信息
    const last = msgs[msgs.length - 1]
    const histMsgs = last && last.role === 'user' && last.content === prompt
      ? msgs.slice(0, -1) : msgs
    const history = buildHistoryWithToolContext(histMsgs)
    const placeholderSender = entMode ? 'orchestrator'
      : target && AGENT_CONFIG[target]
        ? target
        : chatMode === 'cloud' ? 'orchestrator' : 'local'
    setMessages([...msgs, { role: 'assistant', content: '', sender: placeholderSender as any, toolCalls: [], msg_id: newMsgId() }])
    thinkingStartRef.current = Date.now()  // 思考时长起点（首个回答 token 结算）

    const { onEvent, onError } = makeStreamHandlers(isClaude || (!entMode && !!dmTarget))
    const controller = streamChat(
      { model, temperature: 0.7, prompt, images: sentImages, history, system_prompt: sysPrompt,
        session_id: sid, claude: isClaude,
        // sweep 审查修复：force_cloud 优先级高于 chat_backend——离线时 chatMode 自动
        // 落 cloud 会把执行窗口请求推去云端兜底（role_hint 冒充执行体），
        // 执行窗口必须关掉 force_cloud 才能真正强制本机
        force_cloud: !isClaude && (chatMode === 'cloud' || entMode) && agentKindRef.current === 'chat',
        reasoning_effort: effort, target_agent: target || undefined, chat_mode: entMode ? 'entertainment' : 'work',
        // 审查修复：执行窗口强制本机（local 语义=离线报错不回退）——用户在主对话
        // 把执行位置设为云端后，执行窗口发送不得被云端兜底冒充智能体
        chat_backend: entMode ? 'cloud' : (agentKindRef.current !== 'chat' ? 'local' : chatBackend) },
      onEvent, onError,
      () => {
        const s = streamRef.current
        streamRef.current = null
        // 会话切换守卫兜底：流结束时 sid 已变（异常路径）→ 不写库、不处理
        if (s && s.sid !== sid) { setLoading(false); return }
        setLoading(false)
        if (autoRead) setAutoReadTick((t) => t + 1)  // 触发最后一条 AI 气泡自动朗读
        // 重新生成回挂：其后消息接回后再落库（全量替换，顺序错了就是数据丢失）
        const restored = restoreAfterRegenerate(messagesRef.current, sid)
        messagesRef.current = restored
        setMessages(restored)
        const finalMsgs = flushVoiceTranscripts(restored)
        // 多窗口 #16：委派块双写（执行日志 → 执行窗口会话，主对话只落任务卡摘要）；
        // 审查修复：保存后把 UI 状态换成剥除后的版本（状态与落库一致，
        // 下一轮不会重复拆分历史委派块；feedback 下标同步重映射）
        void (async () => {
          const { decoded, split } = await persistSession(finalMsgs, sid, title)
          // sweep 审查修复：替换 UI 前校验尾部同一性——persist 的 await 期间
          // 用户可能已发出下一条消息（或 syncPoll 合入对端消息），此时整组替换
          // 会把新消息抹掉；尾部不匹配则放弃替换（状态保留，库里已是摘要版）
          if (split && sidRef.current === sid) {
            const cur = messagesRef.current
            const tailSame = cur.length === finalMsgs.length
              && cur.every((m, i) => m === finalMsgs[i])
            if (tailSame) {
              messagesRef.current = decoded
              setMessages(decoded)
              setFeedbackState((p) => remapFeedback(p, cur, decoded))
            }
          }
          // 会话日期更新（2026-10-19 修复）：等 /chat/save 落库提交后再刷新列表——
          // 此前未 await，列表查询先于保存提交返回旧 update_time，旧对话日期永不更新
          refreshSessions()
          window.dispatchEvent(new Event('yuan-ctx-refresh'))  // 上下文用量徽标即时刷新
        })()
      },
      false,
      // #28（2026-11-14）：SSE 自动重连——重试前重置占位气泡（新流从头续显，
      // 旧 token/工具卡清掉防重复；落库因消息 id 幂等不受影响）
      () => {
        setMessages((prev) => {
          const next = [...prev]
          const last = next[next.length - 1]
          if (last && last.role === 'assistant') {
            next[next.length - 1] = { ...last, content: '', toolCalls: [], reasoning: '', finalReasoning: '' }
          }
          messagesRef.current = next
          return next
        })
      },
    )
    streamRef.current = { sid, controller }
  }

  const handleSend = (textOverride?: string, voiceMsgId?: string) => {
    const text = (textOverride ?? input).trim()
    if (!currentSid) { flashNotice('请先选择或创建一个会话'); return }
    // sweep 审查修复：历史加载失败时禁止发送——/chat/save 全量替换会清空既有历史
    if (loadFailed) { flashNotice('历史加载失败：直接发送会覆盖本会话历史，请刷新页面重试'); return }
    if (loading) { flashNotice('正在生成中，可点击「停止」或等待完成'); return }
    if (!text) return
    const sentImages = images.length > 0 ? [...images] : undefined
    // voiceMsgId：语音发送复用转录落库的 msg_id（单一写路径——save upsert 幂等、
    // 轮询去重生效；2026-11-16 修复「语音消息显示两遍」根因）；
    // 普通消息创建即赋 id（2026-11-18 修复「整段对话重复 12 遍」：保存时才补 id
    // 在 X5 等环境每次生成新 id，历史全量重插）
    const prevMsgs = [...messages, {
      role: 'user' as const, content: text, images: sentImages,
      msg_id: voiceMsgId || newMsgId(),
    }]
    setMessages(prevMsgs)
    setSendTick((t) => t + 1)
    setImages([]); setInput('')
    sendMessages(prevMsgs, text, sentImages)
  }

  // 修改用户消息：替换内容 → 截断其后所有消息 → 重新发送
  const handleEditMessage = (index: number, newContent: string) => {
    if (loading || !newContent.trim() || !currentSid) return
    // 2026-10-25 数据保护：修改会截断其后所有消息（语义必然）——有后续消息时
    // 先确认，避免误触静默丢对话（重新生成已改为只替换本条，不再截断）
    const dropCount = messages.length - index - 1
    if (dropCount > 0 && !window.confirm(`修改后将清空其后 ${dropCount} 条消息并重新生成，确定继续？`)) return
    const base = [...messages]
    base[index] = { ...base[index], content: newContent.trim() }
    const truncated = base.slice(0, index + 1)
    // #30：被截断消息的 id 进显式删除列表（落库时按 id 删，不再依赖全量替换）
    const dropped = messages.slice(index + 1)
    pendingDeletedIdsRef.current = dropped.map((m) => m.msg_id).filter((x): x is string => !!x)
    setMessages(truncated)
    // 2026-10-19 修复：与重新生成同规则——截断其后消息的点赞/点踩态一并清理，
    // 否则孤儿点赞挂到随后新建的助手消息上
    setFeedbackState((p) => {
      const next = { ...p }
      // #30：被截断消息的反馈键（msg_id 或下标）一并清理
      const dropKeys = new Set(dropped.map((m) => (m.msg_id || String(messages.indexOf(m)))).filter(Boolean))
      Object.keys(next).forEach((k) => { if (dropKeys.has(k) || Number(k) > index) delete next[k] })
      return next
    })
    setSendTick((t) => t + 1)
    setEditingIndex(null)
    sendMessages(truncated, newContent.trim(), base[index].images)
  }

  // 重新生成（AI 气泡，点踩后）：只替换本条气泡——其后的对话保留（2026-10-25
  // 修复：此前截断其后所有消息 = 静默数据丢失）；重发它前面的最后一条用户消息
  // （复用修改重发的 SSE 链路；Claude 桥接模式同修改重发一样是续接语义，
  // 无法真正回退）
  const handleRegenerate = (index: number) => {
    if (loading || !currentSid) return
    const ai = messages[index]
    if (!ai || ai.role !== 'assistant') return
    let ui = -1
    for (let i = index - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { ui = i; break }
    }
    if (ui < 0) return  // 前面没有用户消息 → 无从重发
    const userMsg = messages[ui]
    const after = messages.slice(index + 1)
    pendingAfterRef.current = after.length ? { sid: currentSid, index, after } : null
    setMessages(messages.slice(0, index))
    // 只清理本条反馈态；其后消息的反馈保留（回挂后按 shift 重映射）
    setFeedbackState((p) => {
      const next = { ...p }
      delete next[index]
      return next
    })
    setEditingIndex(null)
    setSendTick((t) => t + 1)
    sendMessages(messages.slice(0, index), String(userMsg.content || ''), (userMsg as any).images)
  }

  // 重新生成回挂（2026-10-25）：流结束后把暂存的其后消息按原序接回，
  // 并重映射反馈下标（新回答气泡数与原来不同时整体平移）
  const restoreAfterRegenerate = (base: ChatMessage[], sid: string): ChatMessage[] => {
    const pa = pendingAfterRef.current
    if (!pa || pa.sid !== sid) return base
    pendingAfterRef.current = null
    const restored = [...base, ...pa.after]
    const shift = base.length - pa.index - 1
    if (shift !== 0) {
      setFeedbackState((p) => {
        const next: typeof p = {}
        Object.entries(p).forEach(([k, v]) => {
          const n = Number(k)
          next[n > pa.index ? n + shift : n] = v
        })
        return next
      })
    }
    return restored
  }

  // 点赞/点踩 三态互斥：乐观更新 + 失败回滚 + pending 防并发（流式期间禁止索引操作）
  // #30（2026-11-14）：反馈按消息 id 定位（msg_id 作键，消息增删不错位）；
  // 旧数据无 id 时回落下标键
  const handleFeedback = async (msgId: string | number, index: number, kind: 'like' | 'dislike') => {
    const key = typeof msgId === 'string' && msgId ? msgId : String(index)
    if (loading || feedbackPendingRef.current.has(key) || !currentSid) return
    const cur = feedback[key] || { liked: false, disliked: false }
    const next = kind === 'like'
      ? { liked: !cur.liked, disliked: false }
      : { liked: false, disliked: !cur.disliked }
    const state = next.liked ? 'like' : next.disliked ? 'dislike' : 'none'
    feedbackPendingRef.current.add(key)
    setFeedbackState((p) => ({ ...p, [key]: next }))
    const ok = await setFeedback(currentSid, index, state, typeof msgId === 'string' ? msgId : undefined)
    if (!ok) setFeedbackState((p) => ({ ...p, [key]: cur }))
    feedbackPendingRef.current.delete(key)
  }

  // ---- 举报（C7 投诉举报机制，2026-10-29）：AI 气泡举报按钮 → 弹窗选原因 → 落工单 ----
  const REPORT_REASONS = ['违法违规内容', '虚假信息', '有害内容', '侵犯个人权益', '其他']
  const [reportIndex, setReportIndex] = useState<number | null>(null)
  const [reportReason, setReportReason] = useState('')
  const [reportDetail, setReportDetail] = useState('')
  const [reportDone, setReportDone] = useState(false)
  const [reportSubmitting, setReportSubmitting] = useState(false)
  const [reportError, setReportError] = useState('')

  const handleReport = (index: number) => {
    if (loading || !currentSid) return
    setReportIndex(index)
    setReportReason('')
    setReportDetail('')
    setReportDone(false)
    setReportError('')
  }

  const submitReport = async () => {
    if (!reportReason || reportIndex === null || !currentSid || reportSubmitting) return
    setReportSubmitting(true)
    setReportError('')
    const reason = reportDetail.trim() ? `${reportReason}：${reportDetail.trim()}` : reportReason
    const ok = await reportMessage(currentSid, reportIndex, reason)
    setReportSubmitting(false)
    if (ok) setReportDone(true)
    else setReportError('提交失败，请稍后重试')
  }

  // 审批决议：Claude 桥接审批走 claude-stream；云端直连审批（V1-2 gate）走 /stream
  const handleDecision = (approve: boolean) => {
    const pa = pendingApproval
    setPendingApproval(null)
    if (!pa || !currentSid) return
    streamChat(
      { model, temperature: 0.7, prompt: '', history: [], system_prompt: sysPrompt,
        session_id: currentSid, decision: { decision_id: pa.decision_id, approve }, claude: pa.claude },
      () => {}, () => {},
      () => { setLoading(false) },
    )
  }

  return (
    <>
    <style>{`
      @media (max-width: 768px) {
        .chat-main { padding: 12px 4px !important; }
        /* 回到底部按钮：手机放大触控目标（36 → 44px，接近触控标准） */
        .yuan-jump-bottom { width: 44px !important; height: 44px !important; bottom: 12px !important; }
        .chat-welcome { padding: 3vh 8px 24px !important; }
        .chat-welcome h1 { font-size: 20px !important; }
        .chat-msg-bubble { max-width: 90% !important; }
        .chat-input-area { padding: 6px 6px 10px !important; }
        .chat-input-inner { max-width: 100% !important; }
        .chat-input-area textarea { font-size: 16px !important; }
        /* 推荐问题横滑一行（手机不换行堆叠） */
        .chat-suggest-row { flex-wrap: nowrap !important; overflow-x: auto !important; padding-bottom: 4px; scrollbar-width: none; }
        .chat-suggest-row::-webkit-scrollbar { display: none; }
      }
      @media (max-width: 480px) {
        .chat-msg-bubble { max-width: 94% !important; font-size: 13px !important; padding: 8px 12px !important; }
        .chat-welcome h1 { font-size: 18px !important; }
        .chat-input-area textarea { font-size: 16px !important; }
        .chat-tool-row { flex-wrap: wrap !important; gap: 6px !important; padding: 0 10px 8px !important; }
        /* 小屏藏低频按钮：下载聊天记录（桌面端悬浮提示按钮） */
        .chat-tool-download { display: none !important; }
        .msg-edit-textarea { font-size: 16px !important; }
      }
      /* 气泡内操作行常显（图标本身 0.65 → 1 hover 微反馈） */
      .msg-actions { opacity: 1; }
      /* 朗读中波形动画 */
      @keyframes msgReadBar {
        0%, 100% { transform: scaleY(0.45); opacity: 0.55; }
        50% { transform: scaleY(1.15); opacity: 1; }
      }
    `}</style>
    <div style={{ height: '100%', display: 'flex', position: 'relative' }}>
      <Sidebar sessions={sessions} currentSid={currentSid} sidebarOpen={sidebarOpen} isMobile={isMobile}
        agents={WINDOW_AGENTS.map((a) => ({ key: a.key, label: a.label, fullLabel: a.fullLabel, color: a.color,
          online: a.onlineKey === 'always' ? true : a.onlineKey === 'claude' ? claudeOnline : localOnline }))}
        activeKind={agentKind} onSwitchKind={handleSwitchKind} showSwitcher={!entMode}
        onNewSession={handleNewSession} onSelect={handleSelectSession} onDelete={handleDeleteSession} onRename={handleRenameSession} onDemoteMain={handleDemoteMain} onOpenTrash={openTrash} onShare={handleShareSession} />

      {sidebarOpen && <div className="mobile-sidebar-backdrop" onClick={() => setSidebarOpen(false)} />}

      <div onClick={() => setSidebarOpen(!sidebarOpen)} className="yuan-tip yuan-tip-down" data-tip={sidebarOpen ? '收起侧栏' : '展开侧栏'} aria-label={sidebarOpen ? '收起侧栏' : '展开侧栏'}
        style={{
          position: 'absolute', left: isMobile ? 0 : (sidebarOpen ? 258 : 0), top: 64, zIndex: 10,
          padding: '12px 4px', borderRadius: '0 8px 8px 0',
          background: 'var(--bg-primary)', cursor: 'pointer', color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
          borderLeft: (!isMobile && sidebarOpen) ? 'none' : '1px solid var(--border)',
          boxShadow: (!isMobile && sidebarOpen) ? '1px 1px 4px var(--shadow-sm)' : '0 1px 3px var(--shadow-sm)',
          lineHeight: 1, transition: 'left 0.2s', display: 'flex', alignItems: 'center',
        }}
      >{sidebarOpen ? <ChevronLeftIcon size={12} /> : <ChevronRightIcon size={12} />}</div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* 后台执行中指示条（多窗口 P3 升级：按智能体分组——计划队列 + CC 执行；
            只显示不动手，点击切到对应执行面） */}
        {(activePlans.length > 0 || (ccBusy && agentKind === 'chat')) && (
          <div style={{
            margin: '8px 16px 0', display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 12px', borderRadius: 8,
            background: 'var(--bg-primary)', border: '1px solid var(--border)',
            fontSize: 12, color: 'var(--text-secondary)',
            boxShadow: '0 1px 3px var(--shadow-sm)',
          }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', background: 'var(--warning)', flexShrink: 0,
              animation: 'pulse 1.2s ease-in-out infinite',
            }} />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
              后台执行中
            </span>
            {activePlans.length > 0 && (
              <span onClick={() => handleOpenPanel('/chat/plan')} className="yuan-tip" data-tip="打开计划面板"
                aria-label="打开计划面板"
                style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', borderRadius: 999, padding: '1px 9px', border: '1px solid var(--border)', lineHeight: 1.7 }}>
                计划 {activePlans.length}
              </span>
            )}
            {ccBusy && agentKind === 'chat' && (
              <span onClick={() => handleSwitchKind('claude')} className="yuan-tip" data-tip="切到 Claude Code 执行窗口"
                aria-label="切到 Claude Code 执行窗口"
                style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', borderRadius: 999, padding: '1px 9px', border: `1px solid ${AGENT_CONFIG.claude.color}`, color: AGENT_CONFIG.claude.color, lineHeight: 1.7 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: AGENT_CONFIG.claude.color, animation: 'pulse 1.2s ease-in-out infinite' }} />
                CC 执行中
              </span>
            )}
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
              {activePlans.length > 0
                ? activePlans.map((p) => `「${p.title}」${p.done_steps}/${p.total_steps}`).join(' · ')
                : (ccActivity?.latest?.message || '')}
            </span>
          </div>
        )}
        {!currentSid ? (
          initFailed ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
              <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>会话加载失败，请检查网络后重试</div>
              <button onClick={() => { setInitFailed(false); window.location.reload() }}
                style={{ padding: '6px 20px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 13, cursor: 'pointer' }}>
                重新加载
              </button>
            </div>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              正在进入对话…
            </div>
          )
        ) : (
          <>
          {wxTip && (
        <div style={{
          margin: '8px 12px 0', padding: '8px 12px', borderRadius: 8,
          background: 'var(--warning-soft)', border: '1px solid var(--warning)',
          fontSize: 12.5, color: 'var(--text-primary)', display: 'flex',
          alignItems: 'center', gap: 8, flexShrink: 0,
        }}>
          <span style={{ flex: 1, lineHeight: 1.6 }}>
            微信内置浏览器对长回复的流式支持不佳，可能出现截断——建议点右上角「···」用系统浏览器打开本页。
          </span>
          <button onClick={dismissWxTip} aria-label="知道了"
            style={{ background: 'none', border: 'none', cursor: 'pointer',
                     color: 'var(--text-muted)', fontSize: 12, flexShrink: 0, padding: '2px 6px' }}>
            知道了
          </button>
        </div>
      )}
      {/* 执行窗口壳（多窗口 P1，2026-11-13）：长任务智能体头部条——身份/在线/最近活动；
          P2 起消息流换执行时间线渲染，本条保留为窗口身份栏 */}
      {agentKind !== 'chat' && (
        <div style={{
          margin: '8px 16px 0', padding: '6px 12px', borderRadius: 8,
          background: 'var(--bg-primary)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)',
          boxShadow: '0 1px 3px var(--shadow-sm)', flexShrink: 0,
        }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: AGENT_CONFIG[agentKind].color, flexShrink: 0 }} />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{AGENT_CONFIG[agentKind].label}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: (agentKind === 'claude' ? claudeOnline : localOnline) ? 'var(--success)' : 'var(--text-muted)',
            }} />
            {(agentKind === 'claude' ? claudeOnline : localOnline) ? '在线' : '离线'}
          </span>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
            {agentKind === 'claude' && ccActivity?.latest
              ? `最近活动 · ${ccActivity.latest.time}`
              : '独立上下文 · 执行过程不占用主对话'}
          </span>
        </div>
      )}
      <ChatView
            messages={messages} loading={loading} user={user}
            agentKind={agentKind}
            setExpandedImage={setExpandedImage}
            input={input} setInput={setInput} handleSend={handleSend}
            images={images} setImages={setImages}
            currentSid={currentSid}
            sessions={sessions}
            dmTarget={dmTargets[currentSid] || ''}
            ccActivity={ccActivity}
            claudeOnline={claudeOnline}
            autoRead={autoRead}
            autoReadTick={autoReadTick}
            pendingApproval={pendingApproval} handleDecision={handleDecision}
            likes={feedback} editingIndex={editingIndex} setEditingIndex={setEditingIndex}
            onEditMessage={handleEditMessage} onFeedback={handleFeedback} onReport={handleReport}
            onRegenerate={handleRegenerate} onContinue={() => handleSend('继续')}
            onStartVoiceCall={startVoiceCallWithPermission}
            entMode={entMode} toggleEntMode={toggleEntMode}
            onStop={stopStream} notice={notice}
            onSuggest={handleSend}
            sendTick={sendTick}
            onOpenPanel={handleOpenPanel}
            onSwitchWindow={handleSwitchKind}
            onOpenSettings={() => handleOpenPanel('/settings')}
          />
      </>
        )}
      </div>

      {/* 回收站弹窗（2026-10-30）：软删除会话列表——恢复/彻底删除 */}
      {trashOpen && (
        <Modal open title="回收站" onClose={() => setTrashOpen(false)}>
          <div style={{ minWidth: 400 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              已删除的对话保留在此可恢复；超过保留期将自动彻底清理。
            </div>
            <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border-light)', borderRadius: 8 }}>
              {trashList.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>回收站为空</div>
              ) : (
                trashList.map((t) => (
                  <div key={t.session_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: '1px solid var(--border-light)' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.title || '未命名'}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>删除于 {t.deleted_at?.slice(0, 16)}</div>
                    </div>
                    <button onClick={() => handleRestoreSession(t.session_id)} disabled={trashBusy}
                      style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid var(--accent)', background: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}>
                      恢复
                    </button>
                    <button onClick={() => handlePurgeSession(t.session_id)} disabled={trashBusy}
                      style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid var(--danger)', background: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 12 }}>
                      彻底删除
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* C7 举报弹窗（2026-10-29）：原因 chip 单选 + 补充说明（选填） */}
      {reportIndex !== null && (
        <Modal open title="举报消息"
          onClose={() => { if (!reportSubmitting) setReportIndex(null) }}>
          {reportDone ? (
            <div style={{ minWidth: 340 }}>
              <div style={{ fontSize: 14, color: 'var(--text-primary)', marginBottom: 12 }}>举报已提交，我们会尽快核实处理。</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>感谢你对内容安全的监督（《生成式AI服务管理暂行办法》第 15 条）。</div>
              <button onClick={() => setReportIndex(null)} className="yuan-tip" data-tip="关闭" aria-label="关闭"
                style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 20px', cursor: 'pointer', fontSize: 13 }}>
                关闭
              </button>
            </div>
          ) : (
            <div style={{ minWidth: 340 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>请选择举报原因</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                {REPORT_REASONS.map((r) => (
                  <button key={r} onClick={() => setReportReason(r)}
                    style={{
                      padding: '5px 12px', borderRadius: 999, fontSize: 12, cursor: 'pointer',
                      border: reportReason === r ? '1px solid var(--accent)' : '1px solid var(--border)',
                      background: reportReason === r ? 'var(--accent-light)' : 'var(--bg-input)',
                      color: reportReason === r ? 'var(--accent)' : 'var(--text-secondary)',
                      transition: 'all 0.15s',
                    }}>{r}</button>
                ))}
              </div>
              <textarea value={reportDetail} onChange={(e) => setReportDetail(e.target.value.slice(0, 300))}
                placeholder="补充说明（选填）"
                rows={3}
                style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', borderRadius: 6,
                  border: '1px solid var(--border)', fontSize: 13, outline: 'none', resize: 'vertical',
                  background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
              {reportError && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 8 }}>{reportError}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
                <button onClick={() => setReportIndex(null)} disabled={reportSubmitting}
                  style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 16px', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>
                  取消
                </button>
                <button onClick={submitReport} disabled={!reportReason || reportSubmitting}
                  style={{ background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', cursor: reportReason && !reportSubmitting ? 'pointer' : 'default', fontSize: 13, fontWeight: 500, opacity: !reportReason || reportSubmitting ? 0.55 : 1 }}>
                  {reportSubmitting ? '提交中...' : '提交举报'}
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {voiceCallOpen && (
        <VoiceCall
          onClose={() => setVoiceCallOpen(false)}
          ensureSession={ensureVoiceSession}
          onTranscript={handleVoiceTranscript}
          onSendText={(text, msgId) => { setInput(''); handleSend(text, msgId) }}
        />
      )}

      {expandedImage && (
        <ZoomableImage src={expandedImage} onClose={() => setExpandedImage(null)} />
      )}

      {/* 子页面面板：桌面=可拖动+可放大缩小浮窗 / 移动=全屏浮层（均不离开对话） */}
      {panel && !isMobile && (() => {
        const resolved = resolvePanel(panel.path)
        if (!resolved) return null
        const pos = planPos || { x: window.innerWidth - 740 - 16, y: 72 }
        const size = planSize || { w: 740, h: 560 }
        const w = Math.max(480, Math.min(size.w, window.innerWidth - 16))
        const h = Math.max(360, Math.min(size.h, window.innerHeight - 80))
        const { Comp, props } = resolved
        return (
          <>
          {/* 点击浮窗外侧关闭（2026-11-14 用户反馈：此前必须点「返回对话」）——
              透明遮罩在浮窗下层，点击即关；不影响浮窗内拖拽/交互 */}
          <div onClick={() => setPanel(null)} aria-hidden="true"
            style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 299, background: 'transparent' }} />
          <div style={{
            position: 'fixed', zIndex: 300,
            left: Math.max(8, Math.min(pos.x, window.innerWidth - 200)),
            top: Math.max(56, Math.min(pos.y, window.innerHeight - 120)),
            width: w, height: h,
            background: 'var(--bg-secondary)', borderRadius: 12,
            boxShadow: '0 12px 48px rgba(0,0,0,0.28)', border: '1px solid var(--border)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            <div
              onPointerDown={(e) => {
                // 关闭按钮不启动拖动（PointerCapture 会吞掉按钮 click）
                if ((e.target as HTMLElement).closest('button')) return
                e.preventDefault()
                const base = planPos || { x: window.innerWidth - 740 - 16, y: 72 }
                planDragRef.current = { startX: e.clientX, startY: e.clientY, baseX: base.x, baseY: base.y }
                ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
              }}
              onPointerMove={(e) => {
                const d = planDragRef.current
                if (!d) return
                setPlanPos({ x: d.baseX + e.clientX - d.startX, y: d.baseY + e.clientY - d.startY })
              }}
              onPointerUp={() => { planDragRef.current = null }}
              style={{
                padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
                cursor: 'grab', userSelect: 'none', touchAction: 'none',
              }}>
              <button onClick={() => setPanel(null)}
                title="返回对话" aria-label="返回对话"
                style={{
                  fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
                  padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)',
                  display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
                  background: 'transparent', cursor: 'pointer', flexShrink: 0,
                }}><ArrowLeftIcon size={12} /> 返回对话</button>
              {/* 浏览器式地址栏：链接地址明文显示，点击复制 */}
              <button onClick={() => {
                const url = window.location.origin + panel.path
                navigator.clipboard.writeText(url).then(() => flashNotice('链接已复制，可直接在浏览器打开')).catch(() => {})
              }}
                title="点击复制此链接（可直接在浏览器打开）" aria-label="复制页面链接"
                style={{
                  flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6,
                  padding: '4px 10px', borderRadius: 999, background: 'var(--bg-input)',
                  border: '1px solid var(--border)', cursor: 'pointer', fontSize: 11,
                  fontFamily: 'monospace', color: 'var(--text-secondary)',
                  overflow: 'hidden', whiteSpace: 'nowrap',
                }}>
                <LinkIcon size={11} style={{ flexShrink: 0 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{window.location.origin}{panel.path}</span>
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>加载中…</div>}>
                <Comp {...props} onClose={() => setPanel(null)} hideBack />
              </Suspense>
            </div>
            {/* 右下角缩放把手：拖动随意放大缩小（最小 480x360，最大到视口边缘） */}
            <div
              onPointerDown={(e) => {
                e.preventDefault()
                e.stopPropagation()
                const base = planSize || { w: 740, h: 560 }
                planResizeRef.current = { startX: e.clientX, startY: e.clientY, baseW: base.w, baseH: base.h }
                ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
              }}
              onPointerMove={(e) => {
                const d = planResizeRef.current
                if (!d) return
                setPlanSize({ w: d.baseW + e.clientX - d.startX, h: d.baseH + e.clientY - d.startY })
              }}
              onPointerUp={() => { planResizeRef.current = null }}
              title="拖动调整大小" aria-label="拖动调整大小"
              style={{
                position: 'absolute', right: 0, bottom: 0, width: 22, height: 22,
                cursor: 'nwse-resize', touchAction: 'none', zIndex: 2,
                display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end',
                padding: '0 3px 3px 0', color: 'var(--text-muted)',
              }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M10 2 L2 10 M10 6 L6 10 M10 10 L10 10" />
              </svg>
            </div>
          </div>
          </>
        )
      })()}
      {panel && isMobile && (() => {
        const resolved = resolvePanel(panel.path)
        if (!resolved) return null
        const { Comp, props } = resolved
        return (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 300,
          background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{
            padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
          }}>
            <button onClick={() => setPanel(null)}
              title="返回对话" aria-label="返回对话"
              style={{
                fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
                padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
                background: 'transparent', cursor: 'pointer',
              }}><ArrowLeftIcon size={12} /> 返回对话</button>
            {/* 浏览器式地址栏：显示独立页面链接，点击复制 */}
            <button onClick={() => {
              const url = window.location.origin + panel.path
              navigator.clipboard.writeText(url).then(() => flashNotice('链接已复制，可直接在浏览器打开')).catch(() => {})
            }}
              title="点击复制此链接（可直接在浏览器打开）" aria-label="复制页面链接"
              style={{
                flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 999, background: 'var(--bg-input)',
                border: '1px solid var(--border)', cursor: 'pointer', fontSize: 11,
                fontFamily: 'monospace', color: 'var(--text-secondary)',
                overflow: 'hidden', whiteSpace: 'nowrap',
              }}>
              <LinkIcon size={11} style={{ flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{window.location.origin}{panel.path}</span>
            </button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>加载中…</div>}>
              <Comp {...props} onClose={() => setPanel(null)} hideBack />
            </Suspense>
          </div>
        </div>
        )
      })()}
    </div>
    </>
  )
}
