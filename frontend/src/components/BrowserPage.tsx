import { useState, useEffect, useRef, useCallback } from 'react'
import { startBrowser, stopBrowser, getBrowserStatus, streamChat, createSession, saveMessages, API_BASE } from '../api'
import ToolCallCard from './ToolCallCard'
import MarkdownContent from './MarkdownContent'
import { executeTool, StatusDot, tabBtnStyle, type Step } from './browser/helpers'
import StepBar from './browser/StepBar'
import Step1Content from './browser/Step1Content'

export default function BrowserPage() {
  const [running, setRunning] = useState(false)
  const [url, setUrl] = useState('')
  const [, setTitle] = useState('')
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [customUrl, setCustomUrl] = useState('')
  const [streamInterval, setStreamInterval] = useState(100)
  const [liveMode, setLiveMode] = useState(true)
  const [browserBusy, setBrowserBusy] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const isXY = url.includes('xyzb.yuanfudao.com')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const [step, setStep] = useState<Step>(1)

  // Audit state
  const [taskCards, setTaskCards] = useState<string[]>(() => {
    try { return JSON.parse(sessionStorage.getItem('xy_cards') || '[]') }
    catch { return [] }
  })
  const [selectedTask, setSelectedTask] = useState('')
  const [auditMessages, setAuditMessages] = useState<{ role: string; content: string; toolCalls?: any[] }[]>([])
  const [auditing, setAuditing] = useState(false)
  const [auditTab, setAuditTab] = useState<'screenshot' | 'audit' | 'logs'>('screenshot')
  const [rejectMode, setRejectMode] = useState(false)
  const [rejectCause, setRejectCause] = useState('')
  const [rejectNotes, setRejectNotes] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [apiResult, setApiResult] = useState<string | null>(null)
  const [taskStarted, setTaskStarted] = useState(false)
  const [currentTaskName, setCurrentTaskName] = useState('')
  const [startingTask, setStartingTask] = useState('')
  const [taskFailCount, setTaskFailCount] = useState(0)
  const [questionImages, setQuestionImages] = useState<{ type: string; data: string }[]>([])
  const [expandedImage, setExpandedImage] = useState<string | null>(null)
  const [auditSessionId, setAuditSessionId] = useState('')

  const ERROR_CAUSES = ['格式问题占比较多', '举报', '文本压线', '黄框压题干', '最终答案', '不独立', '出框', '少答案', '字太小', '答案错']

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString()
    setLogs((prev) => [`${t} ${msg}`, ...prev].slice(0, 50))
  }, [])

  const pollStatus = useCallback(async () => {
    const status = await getBrowserStatus()
    setRunning(status.running)
    setUrl(status.url || '')
    setTitle(status.title || '')
    if (!status.running) {
      setScreenshot(null)
    }
  }, [])

  useEffect(() => {
    pollStatus()
    const id = setInterval(pollStatus, 3000)
    return () => clearInterval(id)
  }, [pollStatus])

  useEffect(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    if (!running || !liveMode) { setScreenshot(null); return }

    const es = new EventSource(`${API_BASE}/browser/stream?interval=${streamInterval / 1000}`)
    esRef.current = es
    es.onmessage = (e) => {
      if (e.data === 'BROWSER_STOPPED') { es.close(); esRef.current = null; setScreenshot(null); return }
      if (e.data.startsWith('ERROR:')) return
      setScreenshot(e.data)
    }
    es.onerror = () => { es.close(); esRef.current = null }
    return () => { es.close(); esRef.current = null }
  }, [running, streamInterval, liveMode])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [auditMessages])

  // Auto-fetch tasks when entering step 2
  useEffect(() => {
    if (step === 2 && isXY) handleGetTasks()
  }, [step, isXY])

  // === Browser Handlers ===
  const handleStart = async () => {
    setBrowserBusy(true)
    const res = await startBrowser()
    addLog(res.message || '启动中...')
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      const status = await getBrowserStatus()
      if (status.running) { setRunning(true); setUrl(status.url || ''); setTitle(status.title || ''); addLog('浏览器就绪'); setBrowserBusy(false); return }
    }
    addLog('浏览器启动超时')
    pollStatus()
    setBrowserBusy(false)
  }

  const handleStop = async () => {
    setBrowserBusy(true)
    const res = await stopBrowser()
    addLog(res.message || '浏览器已关闭')
    pollStatus()
    setBrowserBusy(false)
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
        setTaskCards(sorted)
        sessionStorage.setItem('xy_cards', JSON.stringify(sorted))
        if (sorted.length > 0) setSelectedTask(sorted[0])
      } catch { setTaskCards([]) }
    }
  }

  const handleStartTask = async (name?: string) => {
    const taskName = name || selectedTask
    if (!taskName) return
    setStartingTask(taskName)
    setCurrentTaskName(taskName)
    addLog(`开始任务: ${taskName}...`)
    const result = await executeTool('start_task', { card_title: taskName })
    if (result.includes('失败')) {
      setTaskFailCount((c) => c + 1)
      addLog(`❌ 任务开始失败 (累计失败 ${taskFailCount + 1} 次)`)
    } else {
      setTaskStarted(true)
      setStep(3)
      addLog(result)
    }
    setStartingTask('')
  }

  const handleGetQuestion = async () => {
    addLog('获取题目信息...')
    const result = await executeTool('get_question_info')
    try {
      const data = JSON.parse(result)
      if (data.images && data.images.length > 0) {
        setQuestionImages(data.images)
        addLog(`获取到 ${data.count} 张图片`)
      }
    } catch {
      addLog(result)
    }
  }

  const handleAudit = async () => {
    setAuditing(true)
    setAuditTab('audit')
    setAuditMessages([{ role: 'assistant', content: '⏳ AI 正在审核中...' }])
    const systemPrompt = `你是一个小猿众包题目审核自动化助手。当前任务：单题标答-审核。操作流程：1. 先调用 scroll_canvas() 向下滚动查看完整题目。2. 然后调用 zoom_question() 缩小视图。3. 滚动/缩放后会更新截图。4. 调用 mark_question_correct() 处理判定。5. 说明你的判断结果。注意：不要提交或驳回任务，等待用户确认。`
    let assistantContent = ''

    if (!auditSessionId) {
      const sid = await createSession()
      setAuditSessionId(sid)
    }

    streamChat(
      { model: 'doubao-seed-2-0-pro-260215', temperature: 0.1, prompt: '请审核这道题。', history: [], system_prompt: systemPrompt },
      (event) => {
        if (event.type === 'token') { assistantContent += event.data; setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { ...last[last.length - 1], content: assistantContent }; return last }) }
        else if (event.type === 'tool_start') { setAuditMessages((prev) => { const last = [...prev]; const calls = last[last.length - 1].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[last.length - 1] = { ...last[last.length - 1], toolCalls: [...calls] }; return last }); addLog(`工具: ${event.data.name}`) }
        else if (event.type === 'tool_end') { setAuditMessages((prev) => { const last = [...prev]; const calls = (last[last.length - 1].toolCalls || []).map((c: any) => c.name === event.data.name ? { ...c, status: 'done' } : c); last[last.length - 1] = { ...last[last.length - 1], toolCalls: calls }; return last }); addLog(`完成: ${event.data.name}`) }
        else if (event.type === 'error') { setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { ...last[last.length - 1], content: `❌ ${event.data}` }; return last }); setAuditing(false) }
      },
      (error) => { setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: `❌ ${error}` }; return last }); setAuditing(false) },
      async () => {
        setAuditing(false)
        addLog('AI 审核完成')
        const sid = auditSessionId || await createSession()
        if (!auditSessionId) setAuditSessionId(sid)
        await saveMessages(sid, [
          { role: 'user', content: `请审核这道题\n任务: ${currentTaskName}\nURL: ${url}` },
          { role: 'assistant', content: assistantContent },
        ])
      },
    )
  }

  const handleCorrect = async () => {
    addLog('标记正确...')
    await executeTool('mark_question_correct')
    await executeTool('submit_task', { action: '提交领下一任务' })
    addLog('完成')
  }

  const handleSubmitReject = async (cause: string) => {
    addLog(`驳回: ${cause}...`)
    await executeTool('submit_task', { action: '整题驳回', reject_reason: cause })
    await executeTool('confirm_rejection')
    addLog('完成')
    setRejectMode(false); setRejectCause('')
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

  const resetStep = () => { setStep(1); setTaskStarted(false); setCurrentTaskName(''); setAuditMessages([]); setRejectMode(false); setRejectCause(''); setRejectNotes('') }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px 20px', gap: 12, boxSizing: 'border-box' }}>
      <StepBar step={step} onStep={setStep} onReset={resetStep} taskName={currentTaskName} />

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* Left panel */}
        <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>自动化控制</h2>

          {/* Step 1: 打开网站 */}
          {step === 1 && (
            <Step1Content
              running={running}
              busy={browserBusy}
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
              onLoadCookies={async () => { const r = await executeTool('load_cookies'); addLog(r); if (r.includes('✅')) setStep(2) }}
              onApiRequest={handleApiRequest}
              setApiUrl={setApiUrl}
            />
          )}

          {/* Step 2: 开始任务 */}
          {step === 2 && isXY && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#f5a623' }}>📋 任务列表</span>
                {taskFailCount > 0 && <span style={{ fontSize: 11, color: '#e53935' }}>失败 {taskFailCount} 次</span>}
              </div>
              <button onClick={async () => { await executeTool('go_home'); addLog('已返回首页') }} className="btn btn-outline btn-block">🏠 回首页</button>
              {taskCards.length > 0 && (
                <div>
                  {taskCards.map((t) => {
                    const isSelected = selectedTask === t
                    const isLoading = startingTask === t
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
          {step === 3 && taskStarted && currentTaskName.includes('单题标答-审核') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1976d2' }}>📌 {currentTaskName}</div>

              {questionImages.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>参考答案</div>
                  <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
                    {questionImages.map((img, i) => (
                      <img key={i} src={img.type === 'base64' ? `data:image/png;base64,${img.data}` : img.data}
                        onClick={() => setExpandedImage(img.type === 'base64' ? `data:image/png;base64,${img.data}` : img.data)}
                        style={{ height: 80, borderRadius: 6, border: '1px solid #ddd', cursor: 'pointer', flexShrink: 0, transition: 'opacity 0.12s' }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* 点击放大模态框 */}
              {expandedImage && (
                <div onClick={() => setExpandedImage(null)}
                  style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                  <img src={expandedImage} style={{ maxWidth: '90%', maxHeight: '90%', borderRadius: 8, boxShadow: '0 4px 40px rgba(0,0,0,0.3)' }} />
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 600, color: '#999', padding: '4px 0', borderBottom: '1px solid #eee' }}>通用</div>

              <button onClick={handleAudit} disabled={auditing} className={`btn btn-warning btn-block${auditing ? ' btn-loading' : ''}`} style={{ padding: '10px 0', fontSize: 14, fontWeight: 600 }}>{auditing ? '审核中...' : '🤖 AI 审核'}</button>

              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={async () => { await executeTool('scroll_canvas', { direction: 'down' }); addLog('已向下滚动') }} disabled={!running} className="btn btn-outline btn-sm" style={{ flex: 1 }}>⬇ 滚动</button>
                <button onClick={async () => { await executeTool('scroll_canvas', { direction: 'up' }); addLog('已向上滚动') }} disabled={!running} className="btn btn-outline btn-sm" style={{ flex: 1 }}>⬆ 滚动</button>
              </div>

              {!auditing && auditMessages.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button onClick={handleCorrect} className="btn btn-success btn-block">✅ 正确，没问题</button>

                  <button onClick={() => setRejectMode(!rejectMode)} className="btn btn-outline-danger btn-block">
                    {rejectMode ? '取消纠正' : '❌ 有误，我来纠正'}
                  </button>
                  {rejectMode && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: 8, background: '#fff5f5', borderRadius: 6, border: '1px solid #fcc' }}>
                      <select value={rejectCause} onChange={(e) => setRejectCause(e.target.value)} style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }}>
                        <option value="">选择错误原因...</option>
                        {ERROR_CAUSES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <textarea value={rejectNotes} onChange={(e) => setRejectNotes(e.target.value)} placeholder="详细说明（可选）..." style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12, resize: 'vertical', minHeight: 40 }} />
                      <button onClick={() => { const fullCause = rejectNotes ? `${rejectCause} - ${rejectNotes}` : rejectCause; handleSubmitReject(fullCause); setRejectNotes('') }} disabled={!rejectCause.trim()} className="btn btn-danger">📤 驳回并提交反馈</button>
                    </div>
                  )}

                  <button onClick={async () => { await executeTool('submit_task', { action: '提交领下一任务' }); addLog('已跳过，下一题') }} className="btn btn-outline btn-block">⏭ 跳过，下一题</button>
                </div>
              )}

              <div style={{ fontSize: 12, fontWeight: 600, color: '#999', padding: '4px 0', borderBottom: '1px solid #eee' }}>本任务特有</div>

              <button onClick={handleGetQuestion} className="btn btn-outline btn-block">🖼 获取题目信息</button>
              <button onClick={async () => { await executeTool('zoom_question'); addLog('已缩小') }} disabled={!running} className="btn btn-outline btn-block">🔍 缩小视图</button>
              <button onClick={async () => { await executeTool('mark_question_correct'); addLog('已标记正确') }} className="btn btn-outline btn-block">✅ 审核正确</button>
              <button onClick={async () => { await executeTool('submit_task', { action: '提交领下一任务' }); addLog('已提交') }} className="btn btn-outline btn-block" style={{ borderColor: '#4caf50', color: '#2e7d32', background: '#e8f5e9' }}>📤 提交领下一任务</button>

              <div style={{ display: 'flex', gap: 4 }}>
                <input placeholder="错误原因..." style={{ flex: 1, padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }} onChange={(e) => setRejectCause(e.target.value)} />
                <button onClick={async () => { if (rejectCause.trim()) { await executeTool('submit_task', { action: '整题驳回', reject_reason: rejectCause }); addLog(`驳回: ${rejectCause}`); setRejectCause('') } }} className="btn btn-outline-danger btn-sm">整题驳回</button>
              </div>
              <button onClick={async () => { await executeTool('confirm_rejection'); addLog('已确认驳回') }} className="btn btn-outline btn-block btn-sm">确认驳回弹窗</button>

            </div>
            )}
          </div>

        {/* Right panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f9f9f9', borderRadius: 6, fontSize: 13, flexShrink: 0 }}>
            <StatusDot ok={running} />
            <span>{running ? '运行中' : '未启动'}</span>
            {running && (
              <button onClick={async () => { await executeTool('refresh_page'); addLog('已刷新') }} title="刷新页面" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: '#666', padding: '2px 4px', flexShrink: 0, lineHeight: 1 }}>🔄</button>
            )}
            {url && (
              <span title={url} style={{ color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, fontSize: 12 }}>{url}</span>
            )}
            <button onClick={() => setLiveMode(!liveMode)} title={liveMode ? '暂停实时流' : '开启实时流'} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: liveMode ? '#4caf50' : '#ccc', padding: '2px 6px', flexShrink: 0, fontWeight: 600, lineHeight: 1 }}>● {liveMode ? '实时' : '暂停'}</button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 11, color: '#999', whiteSpace: 'nowrap' }}>间隔</span>
              <input
                type="range" min={10} max={600} step={10}
                value={streamInterval}
                onChange={(e) => setStreamInterval(Number(e.target.value))}
                style={{ width: 50, cursor: 'pointer', margin: 0 }}
              />
              <span style={{ fontSize: 11, color: '#666', minWidth: 28 }}>{streamInterval}ms</span>
            </div>
            <div style={{ display: 'flex', gap: 2, marginLeft: 4 }}>
              <button onClick={() => setAuditTab('screenshot')} style={tabBtnStyle(auditTab === 'screenshot')}>截图</button>
              <button onClick={() => setAuditTab('audit')} style={tabBtnStyle(auditTab === 'audit')}>AI自动化</button>
              <button onClick={() => setAuditTab('logs')} style={tabBtnStyle(auditTab === 'logs')}>日志</button>
            </div>
          </div>

          <div style={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 8, overflow: 'hidden', background: '#fafafa', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
            {auditTab === 'screenshot' && (
              screenshot ? (
                <img src={`data:image/jpeg;base64,${screenshot}`} alt="截图" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              ) : (
                <span style={{ color: '#ccc', fontSize: 14 }}>{running ? '等待截图...' : '浏览器未启动'}</span>
              )
            )}
            {auditTab === 'audit' && (
              <div style={{ width: '100%', height: '100%', overflowY: 'auto', padding: 16, boxSizing: 'border-box' }}>
                {auditMessages.length === 0 ? (
                  <div style={{ textAlign: 'center', color: '#ccc', marginTop: 60, fontSize: 14 }}>点击左侧 "🤖 AI 审核" 开始</div>
                ) : (
                  auditMessages.map((msg, i) => (
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
                        {msg.toolCalls?.map((tc, j) => <ToolCallCard key={j} call={tc} />)}
                      </div>
                    </div>
                  ))
                )}
                <div ref={chatEndRef} />
              </div>
            )}
            {auditTab === 'logs' && (
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
