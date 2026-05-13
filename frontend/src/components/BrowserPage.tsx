import { useState, useEffect, useRef, useCallback, useReducer } from 'react'
import { startBrowser, stopBrowser, getBrowserStatus, streamChat, createSession, saveMessages, loadMessages, API_BASE, getStoredModel } from '../api'
import ToolCallCard from './ToolCallCard'
import MarkdownContent from './MarkdownContent'
import { executeTool, StatusDot, tabBtnStyle, type Step } from './browser/helpers'
import StepBar from './browser/StepBar'
import Step1Content from './browser/Step1Content'
import {
  browserReducer, initialBrowserState,
  workflowReducer, initialWorkflowState,
} from './browser/reducers'

export default function BrowserPage() {
  const [browser, dispatchBrowser] = useReducer(browserReducer, initialBrowserState)
  const [wf, dispatchWf] = useReducer(workflowReducer, initialWorkflowState)

  const [logs, setLogs] = useState<string[]>([])
  const [customUrl, setCustomUrl] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [apiResult, setApiResult] = useState<string | null>(null)
  const [autoStarting, setAutoStarting] = useState(false)
  const [auditStats, setAuditStats] = useState({ correct: 0, reject: 0, skip: 0 })

  // 加载今日审核统计
  useEffect(() => {
    const today = getLocalDate()
    const sid = localStorage.getItem(`audit_session_${today}`)
    if (!sid) return
    loadMessages(sid).then((msgs) => {
      if (!msgs) return
      let correct = 0, reject = 0, skip = 0
      for (const m of msgs) {
        if (m.role !== 'user') continue
        if (m.content.includes('审核正确')) correct++
        else if (m.content.includes('审核有误')) reject++
        else if (m.content.includes('已跳过')) skip++
      }
      setAuditStats({ correct, reject, skip })
    }).catch(() => {})
  }, [wf.step])

  const esRef = useRef<EventSource | null>(null)
  const autoStartCancelRef = useRef(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const isXY = browser.url.includes('xyzb.yuanfudao.com')
  const token = localStorage.getItem('token') || ''
  const addToken = (url: string) => url.startsWith('/api/v1/') && !url.includes('?token=') ? `${url}?token=${token}` : url
  const ERROR_CAUSES = ['格式问题占比较多', '举报', '文本压线', '黄框压题干', '最终答案', '不独立', '出框', '少答案', '字太小', '答案错']

  function getLocalDate(): string {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  const getDailyAuditSessionId = useCallback(async (): Promise<string> => {
    const today = getLocalDate()
    const key = `audit_session_${today}`
    const cached = localStorage.getItem(key)
    if (cached) return cached
    const sid = await createSession(`📋 每日审核 ${getLocalDate()}`)
    localStorage.setItem(key, sid)
    return sid
  }, [])

  // 关键工作流状态持久化到 sessionStorage，切换侧边栏不丢失
  useEffect(() => {
    localStorage.setItem('xy_step', JSON.stringify(wf.step))
    localStorage.setItem('xy_task_started', JSON.stringify(wf.taskStarted))
    localStorage.setItem('xy_current_task_name', JSON.stringify(wf.currentTaskName))
    localStorage.setItem('xy_selected_task', JSON.stringify(wf.selectedTask))
    localStorage.setItem('xy_task_fail_count', JSON.stringify(wf.taskFailCount))
  }, [wf.step, wf.taskStarted, wf.currentTaskName, wf.selectedTask, wf.taskFailCount])

  // 进入 step 3 或切到 AI自动化 tab 时，同步加载当天审核会话的历史消息
  useEffect(() => {
    if (wf.step !== 3 || browser.auditTab !== 'audit' || wf.auditing) return
    const today = getLocalDate()
    const sid = localStorage.getItem(`audit_session_${today}`)
    if (!sid) return
    loadMessages(sid).then((msgs) => {
      if (msgs && msgs.length > 0) {
        dispatchWf({ type: 'SET_AUDIT_MESSAGES', payload: msgs })
      }
    }).catch(() => {})
  }, [wf.step, browser.auditTab, wf.auditing])

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString()
    setLogs((prev) => [`${t} ${msg}`, ...prev].slice(0, 50))
  }, [])

  const pollStatus = useCallback(async () => {
    const status = await getBrowserStatus()
    dispatchBrowser({ type: 'SET_RUNNING', payload: status.running })
    dispatchBrowser({ type: 'SET_URL', payload: status.url || '' })
    if (!status.running) {
      dispatchBrowser({ type: 'SET_SCREENSHOT', payload: null })
    }
  }, [])

  useEffect(() => {
    pollStatus()
    const id = setInterval(pollStatus, 3000)
    return () => clearInterval(id)
  }, [pollStatus])

  useEffect(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    if (!browser.running || !browser.liveMode) { dispatchBrowser({ type: 'SET_SCREENSHOT', payload: null }); return }

    let cancelled = false
    const token = localStorage.getItem('token') || ''
    fetch(`${API_BASE}/browser/sse-token`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(({ token: sseToken }) => {
        if (cancelled) return
        const es = new EventSource(`${API_BASE}/browser/stream?interval=${browser.streamInterval / 1000}&token=${sseToken}`)
        esRef.current = es
        es.onmessage = (e) => {
          if (e.data === 'BROWSER_STOPPED') { es.close(); esRef.current = null; dispatchBrowser({ type: 'SET_SCREENSHOT', payload: null }); return }
          if (e.data.startsWith('ERROR:')) return
          dispatchBrowser({ type: 'SET_SCREENSHOT', payload: e.data })
        }
        es.onerror = () => { es.close(); esRef.current = null }
      })
      .catch(() => {})
    return () => { cancelled = true; esRef.current?.close(); esRef.current = null }
  }, [browser.running, browser.streamInterval, browser.liveMode])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [wf.auditMessages])

  // Auto-fetch tasks when entering step 2
  useEffect(() => {
    if (wf.step === 2 && isXY) handleGetTasks()
  }, [wf.step, isXY])

  // === Browser Handlers ===
  const handleStart = async () => {
    dispatchBrowser({ type: 'SET_BROWSER_BUSY', payload: true })
    const res = await startBrowser()
    addLog(res.message || '启动中...')
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      const status = await getBrowserStatus()
      if (status.running) { dispatchBrowser({ type: 'SET_RUNNING', payload: true }); dispatchBrowser({ type: 'SET_URL', payload: status.url || '' }); addLog('浏览器就绪'); dispatchBrowser({ type: 'SET_BROWSER_BUSY', payload: false }); return }
    }
    addLog('浏览器启动超时')
    pollStatus()
    dispatchBrowser({ type: 'SET_BROWSER_BUSY', payload: false })
  }

  const handleStop = async () => {
    dispatchBrowser({ type: 'SET_BROWSER_BUSY', payload: true })
    const res = await stopBrowser()
    addLog(res.message || '浏览器已关闭')
    pollStatus()
    dispatchBrowser({ type: 'SET_BROWSER_BUSY', payload: false })
  }

  const handleNavigate = async (name: string) => {
    addLog(`正在打开 ${name}...`)
    await executeTool('open_website_by_name', { name })
    addLog(`已打开 ${name}`)
    setTimeout(pollStatus, 1000)
  }

  const handleCustomUrl = async () => {
    if (!customUrl.trim()) return
    addLog(`正在打开 ${customUrl}...`)
    await executeTool('open_custom_url', { url: customUrl })
    addLog(`已打开 ${customUrl}`)
    setCustomUrl('')
    setTimeout(pollStatus, 1000)
  }

  // === XiaoYuan Handlers ===
  const handleGetTasks = async () => {
    addLog('获取任务列表...')
    const result = await executeTool('get_task_cards')
    addLog(result)
    const titles = result.split('\n').find(l => l.includes('所有标题'))
    if (titles) {
      try {
        const str = (titles.split('：')[1] || '[]').replace(/'/g, '"')
        const arr = JSON.parse(str)
        const sorted = Array.isArray(arr) ? [...arr].reverse() : []
        dispatchWf({ type: 'SET_TASK_CARDS', payload: sorted })
        localStorage.setItem('xy_cards', JSON.stringify(sorted))
        if (sorted.length > 0) dispatchWf({ type: 'SET_SELECTED_TASK', payload: sorted[0] })
      } catch { dispatchWf({ type: 'SET_TASK_CARDS', payload: [] }) }
    }
  }

  const handleStartTask = async (name?: string) => {
    const taskName = name || wf.selectedTask
    if (!taskName) return
    dispatchWf({ type: 'SET_STARTING_TASK', payload: taskName })
    dispatchWf({ type: 'SET_CURRENT_TASK_NAME', payload: taskName })
    addLog(`开始任务: ${taskName}...`)
    const result = await executeTool('start_task', { card_title: taskName })
    if (result.includes('失败')) {
      dispatchWf({ type: 'INCREMENT_TASK_FAIL' })
      addLog(`❌ 任务开始失败`)
      dispatchWf({ type: 'SET_STARTING_TASK', payload: '' })
      return false
    }
    dispatchWf({ type: 'SET_TASK_STARTED', payload: true })
    dispatchWf({ type: 'SET_STEP', payload: 3 })
    addLog(result)
    dispatchWf({ type: 'SET_STARTING_TASK', payload: '' })
    return true
  }

  const handleAutoStart = async () => {
    const taskName = wf.taskCards.find(t => t.includes('单题标答-审核'))
    if (!taskName) {
      addLog('⚠️ 未找到单题标答-审核任务')
      return
    }
    setAutoStarting(true)
    autoStartCancelRef.current = false
    dispatchWf({ type: 'SET_TASK_FAIL_COUNT', payload: 0 })
    addLog(`🤖 自动开始: ${taskName}`)
    for (let i = 0; i < 30; i++) {
      if (autoStartCancelRef.current) {
        addLog('⏹ 自动开始已停止')
        break
      }
      const ok = await handleStartTask(taskName)
      if (ok) break
      await new Promise(r => setTimeout(r, 2000))
    }
    setAutoStarting(false)
  }

  const handleStopAutoStart = () => {
    autoStartCancelRef.current = true
    setAutoStarting(false)
    addLog('⏹ 已停止自动开始')
  }

  const handleGetQuestion = async () => {
    addLog('获取题目信息...')
    const result = await executeTool('get_question_info')
    try {
      const data = JSON.parse(result)
      if (data.images && data.images.length > 0) {
        dispatchWf({ type: 'SET_QUESTION_IMAGES', payload: data.images })
        addLog(`获取到 ${data.count} 张图片`)
      }
    } catch {
      addLog(result)
    }
  }

  const handleAudit = async () => {
    dispatchWf({ type: 'SET_AUDITING', payload: true })
    dispatchBrowser({ type: 'SET_AUDIT_TAB', payload: 'audit' })
    dispatchWf({ type: 'SET_AUDIT_MESSAGES', payload: [{ role: 'assistant', content: '⏳ AI 正在审核中...' }] })
    const systemPrompt = `你是一个中小学题目标注审核专家。当前任务：单题标答-审核。

审核标准：从严判断。只要有一处不符合规范，就判错误。不要给"勉强可以"的通过，宁可严不可松。

核心审核规则（逐条对照，违反任一条即驳回）：
- 独立批改答案仅限数学科目，只需补充最终结果，不得复制全部解析文本
- 黄框批改答案有多结果时，只选其中一个补充，保证答案唯一
- 长文本（超15字）已填写或未填写均不算错，无需驳回
- 答案位置居中/居左/居右均为正确，无需驳回
- 数学选择题无作答区域、语文副科无作答区域 → 应举报
- 题干显示不全、答案不全 → 应举报
- 纯画图题 → 应举报
- 判断结果须给出具体错误类型：格式问题/答案错误/黄框压题干/不独立/出框/少答案/字太小

审核时请逐步推理：
1. 观察截图 → 题干完整吗？题目是什么科目？有没有作答区域？
2. 对照规则 → 独立批改答案只适用数学无作答区域题；长文本(超15字)不算错
3. 逐一挑刺 → 答案唯一吗？独立吗？出框吗？压线吗？字太小吗？多结果只选了一个吗？
4. 下结论 → 以上任一项不满足即为错误，给出具体错误类型。只有全部通过才算正确。

操作流程：
1. 调用 get_question_info() 获取题目截图和参考答案
2. 如题干显示不全，调用 scroll_canvas() 或 zoom_question()，重新获取截图
3. 看清完整题目后，对比参考答案，按上述规则逐条判断
4. 正确则调用 mark_question_correct()；错误则指出具体问题和驳回原因

错误处理：
- [可重试] 错误 → 稍等后重试，最多3次
- [致命] 错误 → 停止操作并告知用户

注意：不要调用 submit_task 或 confirm_rejection，等待用户手动确认。`
    let assistantContent = ''
    const sid = await getDailyAuditSessionId()

    let history: { role: string; content: string }[] = []
    try {
      const msgs = await loadMessages(sid)
      if (msgs && msgs.length > 0) {
        // 取最近 20 条作为上下文，过滤掉太长的内容
        history = msgs.slice(-20).map((m: any) => ({ role: m.role, content: (m.content || '').slice(0, 2000) }))
      }
    } catch {}

    streamChat(
      { model: getStoredModel(), temperature: 0.1, prompt: '请严格按照核心审核规则审核这道题，判断标注是否正确，如有错误指出具体驳回原因。', history, system_prompt: systemPrompt },
      (event) => {
        if (event.type === 'token') { assistantContent += event.data; dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: assistantContent } }) }
        else if (event.type === 'tool_start') { dispatchWf({ type: 'APPEND_TOOL_CALL', payload: { name: event.data.name } }); addLog(`工具: ${event.data.name}`) }
        else if (event.type === 'tool_end') { dispatchWf({ type: 'MARK_TOOL_CALL_DONE', payload: event.data.name }); addLog(`完成: ${event.data.name}`) }
        else if (event.type === 'error') { dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: `❌ ${event.data}` } }); dispatchWf({ type: 'SET_AUDITING', payload: false }) }
      },
      (error) => { dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: `❌ ${error}` } }); dispatchWf({ type: 'SET_AUDITING', payload: false }) },
      async () => {
        dispatchWf({ type: 'SET_AUDITING', payload: false })
        addLog('AI 审核完成')
        await saveMessages(sid, [
          { role: 'user', content: `请审核这道题\n任务: ${wf.currentTaskName}\nURL: ${browser.url}` },
          { role: 'assistant', content: assistantContent },
        ], `📋 每日审核 ${getLocalDate()}`)
      },
      true)
  }

  const handleAuditChat = async (text: string) => {
    if (!text.trim() || wf.auditing) return
    dispatchWf({ type: 'ADD_AUDIT_MESSAGE', payload: { role: 'user', content: text } })
    dispatchWf({ type: 'SET_AUDIT_INPUT', payload: '' })
    dispatchWf({ type: 'SET_AUDITING', payload: true })
    dispatchBrowser({ type: 'SET_AUDIT_TAB', payload: 'audit' })
    const systemPrompt = `你是一个自动化助手。当前页面: ${browser.url}\n任务: ${wf.currentTaskName}\n你可以调用工具来帮助用户。工具返回 [可重试] 时请重试最多3次，返回 [致命] 时请停止。`
    let assistantContent = ''
    const sid = await getDailyAuditSessionId()

    let history: { role: string; content: string }[] = []
    try {
      const msgs = await loadMessages(sid)
      if (msgs && msgs.length > 0) {
        history = msgs.slice(-20).map((m: any) => ({ role: m.role, content: (m.content || '').slice(0, 2000) }))
      }
    } catch {}

    dispatchWf({ type: 'ADD_AUDIT_MESSAGE', payload: { role: 'assistant', content: '', toolCalls: [] } })
    streamChat(
      { model: getStoredModel(), temperature: 0.1, prompt: text, history, system_prompt: systemPrompt },
      (event) => {
        if (event.type === 'token') { assistantContent += event.data; dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: assistantContent } }) }
        else if (event.type === 'tool_start') { dispatchWf({ type: 'APPEND_TOOL_CALL', payload: { name: event.data.name } }); addLog(`工具: ${event.data.name}`) }
        else if (event.type === 'tool_end') { dispatchWf({ type: 'MARK_TOOL_CALL_DONE', payload: event.data.name }); addLog(`完成: ${event.data.name}`) }
        else if (event.type === 'error') { dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: `❌ ${event.data}` } }); dispatchWf({ type: 'SET_AUDITING', payload: false }) }
      },
      (error) => { dispatchWf({ type: 'UPDATE_LAST_AUDIT_MESSAGE', payload: { content: `❌ ${error}` } }); dispatchWf({ type: 'SET_AUDITING', payload: false }) },
      async () => {
        dispatchWf({ type: 'SET_AUDITING', payload: false })
        addLog('对话完成')
        await saveMessages(sid, [
          { role: 'user', content: text },
          { role: 'assistant', content: assistantContent },
        ], `📋 每日审核 ${getLocalDate()}`)
      },
      true)
  }

  const saveFeedbackToChat = async (feedback: string) => {
    dispatchWf({ type: 'ADD_AUDIT_MESSAGE', payload: { role: 'user', content: feedback } })
    try {
      const sid = await getDailyAuditSessionId()
      await saveMessages(sid, [{ role: 'user', content: feedback }])
    } catch {}
  }

  const handleSubmitTask = async (action: string, rejectReason?: string) => {
    const result = await executeTool('submit_task', { action, ...(rejectReason ? { reject_reason: rejectReason } : {}) })
    addLog(result)
    if (result.includes('任务终止') || result.includes('需手动处理')) {
      addLog('⚠️ 任务不足，返回任务列表')
      dispatchWf({ type: 'SET_TASK_STARTED', payload: false })
      dispatchWf({ type: 'SET_CURRENT_TASK_NAME', payload: '' })
      dispatchWf({ type: 'SET_AUDIT_MESSAGES', payload: [] })
      dispatchWf({ type: 'SET_QUESTION_IMAGES', payload: [] })
      dispatchWf({ type: 'SET_REJECT_MODE', payload: false })
      dispatchWf({ type: 'SET_REJECT_CAUSE', payload: '' })
      dispatchWf({ type: 'SET_REJECT_NOTES', payload: '' })
      dispatchWf({ type: 'SET_AUDIT_INPUT', payload: '' })
      dispatchWf({ type: 'SET_STEP', payload: 2 })
      setTimeout(() => handleGetTasks(), 500)
    }
  }

  const handleCorrect = async () => {
    addLog('标记正确...')
    await executeTool('mark_question_correct')
    await handleSubmitTask('提交领下一任务')
    await saveFeedbackToChat(`✅ 审核正确，已提交 — 任务: ${wf.currentTaskName}`)
    addLog('完成')
  }

  const handleSubmitReject = async (cause: string) => {
    addLog(`驳回: ${cause}...`)
    await handleSubmitTask('整题驳回', cause)
    await executeTool('confirm_rejection')
    await saveFeedbackToChat(`❌ 审核有误，已驳回 — 原因: ${cause} — 任务: ${wf.currentTaskName}`)
    addLog('完成')
    dispatchWf({ type: 'SET_REJECT_MODE', payload: false })
    dispatchWf({ type: 'SET_REJECT_CAUSE', payload: '' })
  }

  const handleApiRequest = async () => {
    if (!apiUrl.trim()) return
    addLog(`请求: ${apiUrl}`)
    try {
      const res = await fetch('/api/v1/spider/request/request', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: apiUrl, retype: 'text' }),
      })
      const data = await res.json()
      if (data.status === 'success') { setApiResult(data.data || ''); addLog('请求成功') }
      else { setApiResult(`失败: ${data.detail || ''}`); addLog('请求失败') }
    } catch (e: any) { setApiResult(`错误: ${e.message}`); addLog(`请求错误: ${e.message}`) }
  }

  const resetStep = () => dispatchWf({ type: 'RESET_WORKFLOW' })

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px 20px', gap: 12, boxSizing: 'border-box' }}>
      <StepBar step={wf.step} onStep={(s) => dispatchWf({ type: 'SET_STEP', payload: s })} onReset={resetStep} taskName={wf.currentTaskName} />

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* Left panel */}
        <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>自动化控制</h2>

          {/* Step 1: 打开网站 */}
          {wf.step === 1 && (
            <Step1Content
              running={browser.running}
              busy={browser.browserBusy}
              customUrl={customUrl}
              apiUrl={apiUrl}
              apiResult={apiResult}
              onStart={handleStart}
              onStop={handleStop}
              onNavigate={handleNavigate}
              onCustomUrl={handleCustomUrl}
              setCustomUrl={setCustomUrl}
              onRefresh={async () => { await executeTool('refresh_page'); addLog('已刷新') }}
              onSaveCookies={async () => { await executeTool('save_cookies'); addLog('Cookie 已保存') }}
              onLoadCookies={async () => { const r = await executeTool('load_cookies'); addLog(r); if (r.includes('✅')) dispatchWf({ type: 'SET_STEP', payload: 2 }) }}
              onApiRequest={handleApiRequest}
              setApiUrl={setApiUrl}
            />
          )}

          {/* Step 2: 开始任务 */}
          {wf.step === 2 && isXY && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#f5a623' }}>📋 任务列表</span>
                {wf.taskFailCount > 0 && <span style={{ fontSize: 11, color: '#e53935' }}>失败 {wf.taskFailCount} 次</span>}
              </div>
              {(auditStats.correct + auditStats.reject + auditStats.skip) > 0 && (
                <div style={{ display: 'flex', gap: 6, padding: '4px 8px', background: '#f0f7ff', borderRadius: 6, fontSize: 11, flexWrap: 'wrap' }}>
                  <span style={{ color: '#666' }}>📊 今日：</span>
                  <span style={{ color: '#2e7d32' }}>✅ {auditStats.correct}</span>
                  <span style={{ color: '#c62828' }}>❌ {auditStats.reject}</span>
                  <span style={{ color: '#f57f17' }}>⏭ {auditStats.skip}</span>
                </div>
              )}
              <div style={{ display: 'flex', gap: 4 }}>
                {autoStarting ? (
                  <button onClick={handleStopAutoStart} className="btn btn-danger btn-block" style={{ flex: 1, fontSize: 13 }}>⏹ 停止</button>
                ) : (
                  <button onClick={handleAutoStart} className="btn btn-warning btn-block" style={{ flex: 1, fontSize: 13 }}>🤖 自动开始</button>
                )}
                <button onClick={async () => { await executeTool('go_home'); addLog('已返回首页') }} className="btn btn-outline btn-sm">🏠</button>
              </div>
              {wf.taskCards.length > 0 && (
                <div>
                  {wf.taskCards.map((t) => {
                    const isSelected = wf.selectedTask === t
                    const isLoading = wf.startingTask === t
                    return (
                      <div key={t} onClick={() => !isLoading && handleStartTask(t)} style={{
                        padding: '6px 10px', borderRadius: 5, cursor: isLoading ? 'wait' : 'pointer', fontSize: 12,
                        background: isLoading ? '#fff3e0' : isSelected ? '#fff3e0' : '#f9f9f9',
                        border: isLoading ? '1px solid #ffb74d' : isSelected ? '1px solid #ffb74d' : '1px solid #eee',
                        marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6,
                        transition: 'all 0.12s',
                        opacity: isLoading ? 0.7 : 1,
                      }}
                        className="task-item"
                        onMouseEnter={(e) => { if (!isSelected && !isLoading) e.currentTarget.style.background = '#f0f0f0' }}
                        onMouseLeave={(e) => { if (!isSelected && !isLoading) e.currentTarget.style.background = '#f9f9f9' }}
                      >
                        <span style={{ fontSize: 11, color: isLoading ? '#f5a623' : isSelected ? '#f5a623' : '#ccc' }}>{isLoading ? '⏳' : '▶'}</span>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{t}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Step 3: 执行任务 */}
          {wf.step === 3 && wf.taskStarted && wf.currentTaskName.includes('单题标答-审核') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1976d2' }}>📌 {wf.currentTaskName}</div>

              {wf.questionImages.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>参考答案</div>
                  <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
                    {wf.questionImages.map((img, i) => (
                      <img key={i} src={img.type === 'base64' ? `data:image/png;base64,${img.data}` : addToken(img.data)}
                        onClick={() => dispatchWf({ type: 'SET_EXPANDED_IMAGE', payload: img.type === 'base64' ? `data:image/png;base64,${img.data}` : addToken(img.data) })}
                        style={{ height: 80, borderRadius: 6, border: '1px solid #ddd', cursor: 'pointer', flexShrink: 0, transition: 'opacity 0.12s' }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* 点击放大模态框 */}
              {wf.expandedImage && (
                <div onClick={() => dispatchWf({ type: 'SET_EXPANDED_IMAGE', payload: null })}
                  style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                  <img src={wf.expandedImage} style={{ maxWidth: '90%', maxHeight: '90%', borderRadius: 8, boxShadow: '0 4px 40px rgba(0,0,0,0.3)' }} />
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 600, color: '#999', padding: '4px 0', borderBottom: '1px solid #eee' }}>通用</div>

              <button onClick={handleAudit} disabled={wf.auditing} className={`btn btn-warning btn-block${wf.auditing ? ' btn-loading' : ''}`} style={{ padding: '10px 0', fontSize: 14, fontWeight: 600 }}>{wf.auditing ? '审核中...' : '🤖 AI 审核'}</button>

              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={async () => { await executeTool('scroll_canvas', { direction: 'down' }); addLog('已向下滚动') }} disabled={!browser.running} className="btn btn-outline btn-sm" style={{ flex: 1 }}>⬇ 滚动</button>
                <button onClick={async () => { await executeTool('scroll_canvas', { direction: 'up' }); addLog('已向上滚动') }} disabled={!browser.running} className="btn btn-outline btn-sm" style={{ flex: 1 }}>⬆ 滚动</button>
              </div>

              {!wf.auditing && wf.auditMessages.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button onClick={handleCorrect} className="btn btn-success btn-block">✅ 正确，没问题</button>

                  <button onClick={() => dispatchWf({ type: 'SET_REJECT_MODE', payload: !wf.rejectMode })} className="btn btn-outline-danger btn-block">
                    {wf.rejectMode ? '取消纠正' : '❌ 有误，我来纠正'}
                  </button>
                  {wf.rejectMode && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: 8, background: '#fff5f5', borderRadius: 6, border: '1px solid #fcc' }}>
                      <select value={wf.rejectCause} onChange={(e) => dispatchWf({ type: 'SET_REJECT_CAUSE', payload: e.target.value })} style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }}>
                        <option value="">选择错误原因...</option>
                        {ERROR_CAUSES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <textarea value={wf.rejectNotes} onChange={(e) => dispatchWf({ type: 'SET_REJECT_NOTES', payload: e.target.value })} placeholder="详细说明（可选）..." style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12, resize: 'vertical', minHeight: 40 }} />
                      <button onClick={() => { const fullCause = wf.rejectNotes ? `${wf.rejectCause} - ${wf.rejectNotes}` : wf.rejectCause; handleSubmitReject(fullCause); dispatchWf({ type: 'SET_REJECT_NOTES', payload: '' }) }} disabled={!wf.rejectCause.trim()} className="btn btn-danger">📤 驳回并提交反馈</button>
                    </div>
                  )}

                  <button onClick={async () => { await handleSubmitTask('提交领下一任务'); await saveFeedbackToChat(`⏭ 已跳过 — 任务: ${wf.currentTaskName}`) }} className="btn btn-outline btn-block">⏭ 跳过，下一题</button>
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 600, color: '#999', padding: '4px 0', borderBottom: '1px solid #eee' }}>本任务特有</div>

              <button onClick={handleGetQuestion} className="btn btn-outline btn-block">🖼 获取题目信息</button>
              <button onClick={async () => { await executeTool('zoom_question'); addLog('已缩小') }} disabled={!browser.running} className="btn btn-outline btn-block">🔍 缩小视图</button>
              <button onClick={async () => { await executeTool('mark_question_correct'); addLog('已标记正确') }} className="btn btn-outline btn-block">✅ 审核正确</button>
              <button onClick={async () => { await handleSubmitTask('提交领下一任务') }} className="btn btn-outline btn-block" style={{ borderColor: '#4caf50', color: '#2e7d32', background: '#e8f5e9' }}>📤 提交领下一任务</button>

              <div style={{ display: 'flex', gap: 4 }}>
                <input placeholder="错误原因..." style={{ flex: 1, padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }} onChange={(e) => dispatchWf({ type: 'SET_REJECT_CAUSE', payload: e.target.value })} />
                <button onClick={async () => { if (wf.rejectCause.trim()) { await handleSubmitTask('整题驳回', wf.rejectCause); await executeTool('confirm_rejection'); addLog(`驳回: ${wf.rejectCause}`); dispatchWf({ type: 'SET_REJECT_CAUSE', payload: '' }) } }} className="btn btn-outline-danger btn-sm">整题驳回</button>
              </div>
              <button onClick={async () => { await executeTool('confirm_rejection'); addLog('已确认驳回') }} className="btn btn-outline btn-block btn-sm">确认驳回弹窗</button>

            </div>
            )}
          </div>

        {/* Right panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f9f9f9', borderRadius: 6, fontSize: 13, flexShrink: 0 }}>
            <StatusDot ok={browser.running} />
            <span>{browser.running ? '运行中' : '未启动'}</span>
            {browser.running && (
              <button onClick={async () => { await executeTool('refresh_page'); addLog('已刷新') }} title="刷新页面" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#666', padding: '2px 4px', flexShrink: 0, lineHeight: 1 }}>🔄</button>
            )}
            {browser.url && (
              <span title={browser.url} style={{ color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, fontSize: 12 }}>{browser.url}</span>
            )}
            <button onClick={() => dispatchBrowser({ type: 'SET_LIVE_MODE', payload: !browser.liveMode })} title={browser.liveMode ? '暂停实时流' : '开启实时流'} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: browser.liveMode ? '#4caf50' : '#ccc', padding: '2px 6px', flexShrink: 0, fontWeight: 600, lineHeight: 1 }}>● {browser.liveMode ? '实时' : '暂停'}</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 11, color: '#999', whiteSpace: 'nowrap' }}>间隔</span>
              <input
                type="range" min={10} max={600} step={10}
                value={browser.streamInterval}
                onChange={(e) => dispatchBrowser({ type: 'SET_STREAM_INTERVAL', payload: Number(e.target.value) })}
                style={{ width: 50, cursor: 'pointer', margin: 0 }}
              />
              <span style={{ fontSize: 11, color: '#666', minWidth: 28 }}>{browser.streamInterval}ms</span>
            </div>
            <div style={{ display: 'flex', gap: 2, marginLeft: 4 }}>
              <button onClick={() => dispatchBrowser({ type: 'SET_AUDIT_TAB', payload: 'screenshot' })} style={tabBtnStyle(browser.auditTab === 'screenshot')}>截图</button>
              <button onClick={() => dispatchBrowser({ type: 'SET_AUDIT_TAB', payload: 'audit' })} style={tabBtnStyle(browser.auditTab === 'audit')}>AI自动化</button>
              <button onClick={() => dispatchBrowser({ type: 'SET_AUDIT_TAB', payload: 'logs' })} style={tabBtnStyle(browser.auditTab === 'logs')}>日志</button>
            </div>
          </div>

          <div style={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 8, overflow: 'hidden', background: '#fafafa', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
            {browser.auditTab === 'screenshot' && (
              browser.screenshot ? (
                <img src={`data:image/jpeg;base64,${browser.screenshot}`} alt="截图" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              ) : (
                <span style={{ color: '#ccc', fontSize: 14 }}>{browser.running ? '等待截图...' : '浏览器未启动'}</span>
              )
            )}
            {browser.auditTab === 'audit' && (
              <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
                  {wf.auditMessages.length === 0 ? (
                    <div style={{ textAlign: 'center', color: '#ccc', marginTop: 60, fontSize: 14 }}>输入消息或点击左侧 "🤖 AI 审核"</div>
                  ) : (
                    wf.auditMessages.map((msg, i) => (
                      <div key={i} style={{ marginBottom: 10, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                        <div style={{
                          padding: '8px 14px', borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '4px 18px 18px 18px',
                          maxWidth: '80%', background: msg.role === 'user' ? '#1976d2' : '#fff',
                          color: msg.role === 'user' ? '#fff' : '#333',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                          whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6,
                          overflowWrap: 'break-word', wordBreak: 'break-word',
                        }}>
                          {msg.role === 'assistant' ? <MarkdownContent content={msg.content} /> : msg.content}
                          {msg.toolCalls?.map((tc: any, j: number) => <ToolCallCard key={j} call={tc} />)}
                        </div>
                      </div>
                    ))
                  )}
                  <div ref={chatEndRef} />
                </div>
                <div style={{ display: 'flex', gap: 6, padding: '8px 12px', borderTop: '1px solid #eee', background: '#fff', flexShrink: 0 }}>
                  <input value={wf.auditInput} onChange={(e) => dispatchWf({ type: 'SET_AUDIT_INPUT', payload: e.target.value })}
                    onKeyDown={(e) => e.key === 'Enter' && handleAuditChat(wf.auditInput)}
                    placeholder="输入指令，如：向下滚动 / 打开知乎 / 帮我审核"
                    disabled={wf.auditing}
                    style={{ flex: 1, padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none' }} />
                  <button onClick={() => handleAuditChat(wf.auditInput)} disabled={wf.auditing || !wf.auditInput.trim()}
                    className={`btn btn-primary${wf.auditing ? ' btn-loading' : ''}`}
                    style={{ padding: '8px 14px', fontSize: 13 }}>发送</button>
                </div>
              </div>
            )}
            {browser.auditTab === 'logs' && (
              <div style={{ width: '100%', height: '100%', overflowY: 'auto', padding: 12, boxSizing: 'border-box' }}>
                {logs.length === 0 ? (
                  <div style={{ textAlign: 'center', color: '#ccc', marginTop: 60, fontSize: 14 }}>暂无操作记录</div>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#666', padding: '3px 0', fontFamily: 'monospace', borderBottom: '1px solid #f0f0f0' }}>{log}</div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
