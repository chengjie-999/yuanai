import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { streamChat, createSession, listSessions, ensureMainSession, deleteSession, loadMessages, saveMessages, loadFeedback, setFeedback, getStoredModel, setStoredModel, getStoredEffort, setStoredEffort, API_BASE, getToken } from '../api'
import type { ChatMessage } from '../types'
import { senderFromTool, AGENT_CONFIG } from '../config/agents'
import { encodeMsg, buildHistoryWithToolContext } from './chat/helpers'
import Sidebar from './chat/Sidebar'
import WelcomePage from './chat/WelcomePage'
import ChatView from './chat/ChatView'
import VoiceCall from './chat/VoiceCall'
import ZoomableImage from './chat/ZoomableImage'
import { useVoiceCall } from './chat/useVoiceCall'
import { usePlanWindow } from './chat/usePlanWindow'
import { useAutoRead } from '../hooks/useAutoRead'
import { ChevronLeftIcon, ChevronRightIcon } from './icons'

type SessionInfo = { session_id: string; title: string; create_time: string; update_time: string; is_main?: boolean }

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
    let pageLink: string | undefined
    let recipient: string | undefined = undefined
    let turn: number | undefined = undefined
    let msgType: any = undefined
    let content = m.content || ''
    if (typeof content === 'string' && content.startsWith('\x00META\x00')) {
      const end = content.indexOf('\x00', 6)
      if (end > 6) {
        try {
          const meta = JSON.parse(content.substring(6, end))
          sender = meta.s; toolCalls = meta.t; reasoning = meta.r
          pageLink = normalizePageLink(meta.p)
          recipient = meta.rp; turn = meta.tn; msgType = meta.ty
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
             reasoning, pageLink, recipient, turn, msgType }
  })
}

export default function ChatPage({ user }: { user?: any }) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [currentSid, setCurrentSid] = useState<string>('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState(getStoredModel)
  // 聊天页模型下拉（输入区工具行）：切换即持久化 localStorage
  const handleModelChange = (v: string) => { setModel(v); setStoredModel(v) }
  const [quickInput, setQuickInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth > 768)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth <= 768)
  const [images, setImages] = useState<string[]>([])
  const [expandedImage, setExpandedImage] = useState<string | null>(null)
  // 聊天模式（内部自动切换，不再暴露下拉框——微信式群聊由 @指定接管）：
  // local=本地统筹 Agent（默认）→ 本地离线时自动落 cloud；claude 模式已并入 @Claude Code
  const [chatMode, setChatMode] = useState<'local' | 'cloud' | 'claude'>('local')
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
  const saveDmTarget = (sid: string, target: string) => {
    setDmTargets((prev) => {
      const next = target ? { ...prev, [sid]: target } : { ...prev }
      localStorage.setItem('dmTargets', JSON.stringify(next))
      return next
    })
  }
  // 推理强度开关（快答/深思）：localStorage 持久化，仅对 DeepSeek 系列生效
  const [effort, setEffortState] = useState<'low' | 'medium' | 'high'>(getStoredEffort())
  const setEffort = (v: 'low' | 'medium' | 'high') => { setEffortState(v); setStoredEffort(v) }
  const [localOnline, setLocalOnline] = useState(false)
  const [claudeOnline, setClaudeOnline] = useState(false)
  const [statusKnown, setStatusKnown] = useState(false)
  // Claude Code 桥接待审批命令
  const [pendingApproval, setPendingApproval] = useState<{ decision_id: string; tool_name: string; command: string } | null>(null)
  // 消息点赞（下标 → 已赞）与修改编辑态（消息下标，null = 非编辑态）
  const [feedback, setFeedbackState] = useState<Record<number, { liked: boolean; disliked: boolean }>>({})
  // 自动朗读（默认开启，与顶部栏喇叭/设置页开关共享 useAutoRead 同步）
  const autoRead = useAutoRead()
  const [autoReadTick, setAutoReadTick] = useState(0)
  const feedbackPendingRef = useRef<Set<number>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  // 发送计数：每次发送/修改重发 +1，ChatView 据此无条件滚底并恢复跟随
  const [sendTick, setSendTick] = useState(0)
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const sidRef = useRef(currentSid)
  sidRef.current = currentSid
  const loadingRef = useRef(loading)
  loadingRef.current = loading

  // 计划面板窗口：用户手动开/关（AI 不自动开关，用户拍板）；协议见 chat/planWindow.ts
  const navigate = useNavigate()
  const planWin = usePlanWindow({ isMobile, navigate })
  const handleOpenPanel = useCallback((_link: string) => { planWin.openPanel() }, [planWin.openPanel])

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
    const list = await listSessions()
    setSessions(list)
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
      const main = await ensureMainSession()
      await refreshSessions()
      if (main && !sidRef.current) {
        setCurrentSid(main.session_id)
        const history = await loadMessages(main.session_id)
        setMessages(history.length === 0
          ? [{ role: 'assistant', content: '你好！有什么可以帮你的？' }]
          : parseHistory(history))
        scrollToLatest()
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshSessions])

  // 语音通话状态机（会话锚定/转录队列/保存快照 flush，独立 hook）
  const {
    voiceCallOpen, setVoiceCallOpen, lastAssistantText,
    ensureVoiceSession, startVoiceCall,
    handleVoiceTranscript, flushVoiceTranscripts, noteLastAssistant,
  } = useVoiceCall({
    sidRef, messagesRef, loadingRef,
    setMessages, setCurrentSid, refreshSessions,
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
    // 新建普通对话并立即打开（登录已直接落主对话，新对话按钮=另开一个会话）
    const sid = await createSession()
    setCurrentSid(sid)
    setMessages([{ role: 'assistant', content: '你好！有什么可以帮你的？' }])
    setQuickInput('')
    setInput('')
    setImages([])
    setFeedbackState({})
    setEditingIndex(null)
    refreshSessions()
  }

  // 长任务小窗：新建独立会话并固定定向该智能体（后续消息持久定向，
  // 不进主对话 60 条截断——claude 走 claude-stream 天然不截断，automation 后端放宽）
  const openDirectChat = async (target: string) => {
    const cfg = AGENT_CONFIG[target]
    if (!cfg) return
    const sid = await createSession(`${cfg.label} 私聊`)
    saveDmTarget(sid, target)
    setTargetAgent(target)
    setCurrentSid(sid)
    setMessages([{ role: 'assistant', content: `已开「${cfg.label}」小窗：本会话内的消息都将直接交给${cfg.label}处理，长任务对话不占用主对话历史。`, sender: target as any, toolCalls: [] }])
    refreshSessions()
  }

  const handleSelectSession = async (sid: string) => {
    setCurrentSid(sid)
    // 小窗会话：恢复持久定向；普通会话：不动（@ 定向单次生效机制不变）
    const dm = dmTargetsRef.current[sid]
    if (dm) setTargetAgent(dm)
    const history = await loadMessages(sid)
    const feedbackData = await loadFeedback(sid)
    setFeedbackState(feedbackData)
    setEditingIndex(null)
    setMessages(history.length === 0
      ? [{ role: 'assistant', content: '你好！有什么可以帮你的？' }]
      : parseHistory(history))
    scrollToLatest()  // 历史异步加载完成后补滚（时序缺口）
  }

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation()
    await deleteSession(sid)
    if (currentSid === sid) { setCurrentSid(''); setMessages([]) }
    refreshSessions()
  }

  const SYSTEM_PROMPT_BASE = '你是小元AI的统筹助手。数据分析、数据采集、生命科学等能力以「脚本工具」（script_ 开头）直接挂在你名下，一次函数调用即可选定脚本并执行，不需要委派。\n\n可直接使用的工具：\n- 脚本工具：script_descriptive_stats（描述性统计）/ script_correlation（相关性）/ script_regression（回归）/ script_categorical（分类数据）/ script_timeseries（时间序列）/ script_preprocess（数据预处理）/ script_rfm_cluster（RFM 分群）/ script_churn_predict（流失预测）/ script_gene_expression（基因表达）/ script_generic_crawl（通用网页采集）\n- create_plan：把多步组合任务（先采集后分析等）拆成草稿计划\n- execute_plan：用户说「执行」时把计划加入队列\n- get_plan_status：查询计划进度\n- search_web：联网搜索（query 用核心短语、词间空格分词；搜出链接后用 fetch_url + parse_html 取详情）\n- retrieve_planet_knowledge：检索用户个人知识星球（导图/笔记，只读）\n- delegate_to_automation_agent：仅浏览器控制/审核等需多步自主操作的任务才委派\n\n计划流（重要）：多步骤组合任务（如「先抓取数据，再做统计分析」）先用 create_plan 制定草稿计划（每步写清 skill 与意图，能确定脚本时填 script 工具名与 params，信息不足先问用户），向用户复述步骤并说明「说『执行』才会开始」；用户明确说执行时再调用 execute_plan。不要用文字代替计划、不要连续自行委派执行。\n\n群聊说话人协议（重要）：历史消息中带【xx Agent】前缀的是其他智能体说过的话，不是你说的；无前缀的 assistant 消息才是你自己说过的。不要复述、冒充或接续别人的话，不要替其他智能体总结其发言。\n\n工作原则：\n1. 判断意图：分析/采集类直接选脚本工具执行，一句话说明在做什么\n2. 工具返回结果后，如果结果已经清晰完整，只做简短确认如"以上是结果"，不要再复述\n3. 只有当结果需要解读、比较或给出建议时，才补充分析\n4. 用户能看到工具输出，重复内容只会让对话冗余\n5. 对话结束或任务完成时，用表格总结本次完成了什么、关键结论是什么'

  const makeStreamHandlers = () => {
    // 本地 Agent 模式气泡显示「小元AI · 本机」，云端模式显示「小元AI」，Claude 模式显示 Claude Code
    let currentSender = chatMode === 'cloud' ? 'orchestrator' : 'local'
    const onEvent = (event: any) => {
      if (event.type === 'token') {
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: last[i].content + event.data, sender: (last[i].sender || currentSender) as any }; return last })
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
            if (last && last.role === 'assistant' && last.sender === ns && !last.content) {
              // 同一 Agent 连续工具调用/重复事件 → 复用气泡
              const calls = [...(last.toolCalls || [])]
              if (!calls.some((c) => c.name === event.data.name && c.status === 'running')) {
                calls.push({ name: event.data.name, status: 'running' as const })
              }
              return [...prev.slice(0, -1), { ...last, toolCalls: calls, pageLink: link || last.pageLink }]
            }
            return [...prev, { role: 'assistant' as const, content: '', sender: ns as any, pageLink: link, toolCalls: [{ name: event.data.name, status: 'running' as const }] }]
          })
        }
        else {
          // 统筹自身工具（含计划工具）：工具卡挂当前气泡；计划工具同时挂
          // 「打开面板」链接（计划工具不独立成泡后，这是 /chat/plan 的入口）
          const isPlanTool = event.data.name === 'create_plan'
            || event.data.name === 'execute_plan' || event.data.name === 'get_plan_status'
          setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) { const calls = last[i].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[i] = { ...last[i], toolCalls: [...calls], pageLink: isPlanTool ? '/chat/plan' : last[i].pageLink } }; return last })
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
            const calls = (last[i].toolCalls || []).map(function (c: any) { return c.name === del_name ? { name: c.name, status: 'done', result: event.data.output || '' } : c })
            last[i] = { role: last[i].role, content: last[i].content, sender: last[i].sender, toolCalls: calls, pageLink: last[i].pageLink, images: last[i].images }
          }
          return last
        })
        if (isDel) {
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
        setPendingApproval({ decision_id: event.data.decision_id, tool_name: event.data.tool_name, command: event.data.command })
      } else if (event.type === 'error') {
        // 展示真实错误信息（截断），便于排查
        const errMsg = typeof event.data === 'string' && event.data ? event.data.slice(0, 300) : '请求失败，请重试'
        setMessages((prev) => { const last = [...prev]; const i = last.length - 1; if (i >= 0) last[i] = { ...last[i], content: `请求失败: ${errMsg}` }; return last }); setLoading(false)
      }
    }
    const onError = (msg?: string) => { setMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: msg || '网络异常，请检查连接' }; return last }); setLoading(false) }
    return { onEvent, onError }
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
    // @指定智能体：发送时捕获并复位（单次生效，下一条恢复统筹自行路由）；
    // 小窗会话（dmTargets）持久定向不复位；@Claude Code = 原 ⌘ 桥接模式
    const dmTarget = dmTargetsRef.current[sid] || ''
    const target = targetAgentRef.current || dmTarget
    if (target && !dmTarget) setTargetAgent('')
    const isClaude = target === 'claude' || chatMode === 'claude'
    // 信封协议：最后一条 user 消息打 recipient（定向 @target）；说话人身份
    // 走信封字段，【xx】前缀渲染由后端 views.py 视图滤波负责
    const taggedMsgs = msgs.map((m, i) => (
      i === msgs.length - 1 && m.role === 'user'
        ? { ...m, recipient: target || undefined, turn: undefined }
        : m
    ))
    const history = buildHistoryWithToolContext(taggedMsgs)
    const placeholderSender = target && AGENT_CONFIG[target]
      ? target
      : chatMode === 'cloud' ? 'orchestrator' : 'local'
    setMessages([...msgs, { role: 'assistant', content: '', sender: placeholderSender as any, toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt, images: sentImages, history, system_prompt: SYSTEM_PROMPT_BASE,
        session_id: isClaude ? sid : undefined, claude: isClaude, force_cloud: !isClaude && chatMode === 'cloud', reasoning_effort: effort, target_agent: target || undefined },
      onEvent, onError,
      () => {
        setLoading(false)
        if (autoRead) setAutoReadTick((t) => t + 1)  // 触发最后一条 AI 气泡自动朗读
        const finalMsgs = flushVoiceTranscripts(messagesRef.current)
        const msgs = finalMsgs.map(encodeMsg)
        // C AI 会话标题：只透传显式 title（新会话首次发送），普通发送不再覆盖标题
        saveMessages(sid, msgs, title)
        noteLastAssistant(finalMsgs)
        refreshSessions()
      },
    )
  }

  const handleSend = (textOverride?: string) => {
    const text = (textOverride ?? input).trim()
    if (!text || loading || !currentSid) return
    const sentImages = images.length > 0 ? [...images] : undefined
    const prevMsgs = [...messages, { role: 'user' as const, content: text, images: sentImages }]
    setMessages(prevMsgs)
    setSendTick((t) => t + 1)
    setImages([]); setInput('')
    sendMessages(prevMsgs, text, sentImages)
  }

  // 修改用户消息：替换内容 → 截断其后所有消息 → 重新发送
  const handleEditMessage = (index: number, newContent: string) => {
    if (loading || !newContent.trim() || !currentSid) return
    const base = [...messages]
    base[index] = { ...base[index], content: newContent.trim() }
    const truncated = base.slice(0, index + 1)
    setMessages(truncated)
    setSendTick((t) => t + 1)
    setEditingIndex(null)
    sendMessages(truncated, newContent.trim(), base[index].images)
  }

  // 重新生成（AI 气泡，点踩后）：截断本条及其后所有消息 → 重发它前面的
  // 最后一条用户消息（复用修改重发的 SSE 链路；Claude 桥接模式同修改重发
  // 一样是续接语义，无法真正回退）
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
    const truncated = messages.slice(0, index)
    setMessages(truncated)
    // 被截断消息的点赞/点踩态一并清理（下标越界孤儿行）
    setFeedbackState((p) => {
      const next = { ...p }
      Object.keys(next).forEach((k) => { if (Number(k) >= index) delete next[Number(k)] })
      return next
    })
    setEditingIndex(null)
    setSendTick((t) => t + 1)
    sendMessages(truncated, String(userMsg.content || ''), (userMsg as any).images)
  }

  // 点赞/点踩 三态互斥：乐观更新 + 失败回滚 + pending 防并发（流式期间禁止索引操作）
  const handleFeedback = async (index: number, kind: 'like' | 'dislike') => {
    if (loading || feedbackPendingRef.current.has(index) || !currentSid) return
    const cur = feedback[index] || { liked: false, disliked: false }
    const next = kind === 'like'
      ? { liked: !cur.liked, disliked: false }
      : { liked: false, disliked: !cur.disliked }
    const state = next.liked ? 'like' : next.disliked ? 'dislike' : 'none'
    feedbackPendingRef.current.add(index)
    setFeedbackState((p) => ({ ...p, [index]: next }))
    const ok = await setFeedback(currentSid, index, state)
    if (!ok) setFeedbackState((p) => ({ ...p, [index]: cur }))
    feedbackPendingRef.current.delete(index)
  }

  // 语音通话结束：刷新会话列表（新会话标题/最近对话）
  const handleVoiceCallEnd = () => {
    refreshSessions()
  }

  // 审批决议：走 Claude 桥接专用流，body 带 decision
  const handleDecision = (approve: boolean) => {
    const pa = pendingApproval
    setPendingApproval(null)
    if (!pa || !currentSid) return
    streamChat(
      { model, temperature: 0.7, prompt: '', history: [], system_prompt: SYSTEM_PROMPT_BASE,
        session_id: currentSid, decision: { decision_id: pa.decision_id, approve }, claude: true },
      () => {}, () => {},
      () => { setLoading(false) },
    )
  }

  const sendWithNewSession = async (text: string) => {
    setLoading(true)
    const sid = await createSession()
    setCurrentSid(sid); refreshSessions()
    setInput(''); setQuickInput('')
    // @指定智能体：发送时捕获并复位（欢迎页新建会话入口同规则）
    const target = targetAgentRef.current
    if (target) setTargetAgent('')
    const isClaude = target === 'claude' || chatMode === 'claude'
    const sentImages = [...images]; setImages([])
    setMessages([{ role: 'user', content: text, images: sentImages.length > 0 ? sentImages : undefined }])
    setSendTick((t) => t + 1)
    const placeholderSender = target && AGENT_CONFIG[target]
      ? target
      : chatMode === 'cloud' ? 'orchestrator' : 'local'
    setMessages((prev) => [...prev, { role: 'assistant', content: '', sender: placeholderSender as any, toolCalls: [] }])

    const { onEvent, onError } = makeStreamHandlers()
    streamChat(
      { model, temperature: 0.7, prompt: text, images: sentImages.length > 0 ? sentImages : undefined, history: [], system_prompt: SYSTEM_PROMPT_BASE,
        session_id: isClaude ? sid : undefined, claude: isClaude, force_cloud: !isClaude && chatMode === 'cloud', reasoning_effort: effort, target_agent: target || undefined },
      onEvent, onError,
      () => {
        setLoading(false)
        if (autoRead) setAutoReadTick((t) => t + 1)
        const finalMsgs = flushVoiceTranscripts(messagesRef.current)
        const msgs = finalMsgs.map(encodeMsg)
        saveMessages(sid, msgs, text.length > 50 ? text.slice(0, 50) + '...' : text)
        noteLastAssistant(finalMsgs)
        refreshSessions()
      },
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
        onNewSession={handleNewSession} onSelect={handleSelectSession} onDelete={handleDeleteSession} />

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
        {/* 后台执行中的计划指示条（只显示不动手；点击由用户手动打开计划面板） */}
        {activePlans.length > 0 && (
          <div style={{
            margin: '8px 16px 0', display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 12px', borderRadius: 8,
            background: 'var(--bg-primary)', border: '1px solid var(--border)',
            cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)',
            boxShadow: '0 1px 3px var(--shadow-sm)',
          }} onClick={() => planWin.openPanel()}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', background: '#d97706', flexShrink: 0,
              animation: 'pulse 1.2s ease-in-out infinite',
            }} />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
              后台执行中（{activePlans.length}）
            </span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
              {activePlans.map((p) => `「${p.title}」${p.done_steps}/${p.total_steps}`).join(' · ')}
            </span>
            <span style={{ whiteSpace: 'nowrap', color: 'var(--accent)' }}>打开计划面板</span>
          </div>
        )}
        {!currentSid ? (
          <WelcomePage
            images={images} setImages={setImages}
            quickInput={quickInput} setQuickInput={setQuickInput}
            sendWithNewSession={sendWithNewSession}
            sessions={sessions} onSelectSession={handleSelectSession}
            chatMode={chatMode} setChatMode={setChatMode}
            localOnline={localOnline} claudeOnline={claudeOnline}
            effort={effort} setEffort={setEffort}
            onStartVoiceCall={startVoiceCallWithPermission}
          />
        ) : (
          <ChatView
            messages={messages} loading={loading} user={user}
            setExpandedImage={setExpandedImage}
            input={input} setInput={setInput} handleSend={handleSend}
            images={images} setImages={setImages}
            currentSid={currentSid}
            sessions={sessions}
            localOnline={localOnline} claudeOnline={claudeOnline}
            model={model} setModel={handleModelChange}
            effort={effort} setEffort={setEffort}
            autoRead={autoRead}
            autoReadTick={autoReadTick}
            pendingApproval={pendingApproval} handleDecision={handleDecision}
            likes={feedback} editingIndex={editingIndex} setEditingIndex={setEditingIndex}
            onEditMessage={handleEditMessage} onFeedback={handleFeedback}
            onRegenerate={handleRegenerate}
            onStartVoiceCall={startVoiceCallWithPermission}
            targetAgent={targetAgent} setTargetAgent={setTargetAgent}
            onOpenDirectChat={openDirectChat}
            onSuggest={handleSend}
            sendTick={sendTick}
            isMobile={isMobile}
            onOpenPanel={handleOpenPanel}
          />
        )}
      </div>

      {voiceCallOpen && (
        <VoiceCall
          onClose={() => { setVoiceCallOpen(false); handleVoiceCallEnd() }}
          ensureSession={ensureVoiceSession}
          onTranscript={handleVoiceTranscript}
          lastAssistantText={lastAssistantText}
        />
      )}

      {expandedImage && (
        <ZoomableImage src={expandedImage} onClose={() => setExpandedImage(null)} />
      )}
    </div>
    </>
  )
}
