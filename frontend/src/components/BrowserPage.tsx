import { useState, useEffect, useRef, useCallback } from 'react'
import { startBrowser, stopBrowser, getBrowserStatus, getBrowserScreenshot, streamChat } from '../api'
import ToolCallCard from './ToolCallCard'
import MarkdownContent from './MarkdownContent'

const API_BASE = '/api/v1'

const WEBSITES = [
  { name: '小猿众包', url: 'https://xyzb.yuanfudao.com/' },
  { name: '知乎', url: 'https://www.zhihu.com/' },
  { name: 'B站', url: 'https://www.bilibili.com/' },
  { name: 'BOSS直聘', url: 'https://www.zhipin.com/' },
]

async function executeTool(name: string, args: any = {}): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/tools/execute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, args }),
    })
    const data = await res.json()
    return data.result || data.detail || '完成'
  } catch { return '调用失败' }
}

function StatusDot({ ok }: { ok: boolean }) {
  return <span style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block', background: ok ? '#4caf50' : '#ccc', marginRight: 6 }} />
}

function opBtnStyle(): React.CSSProperties {
  return { padding: '5px 10px', borderRadius: 4, border: '1px solid #ddd', background: '#fff', cursor: 'pointer', fontSize: 11, color: '#333' }
}

function actionBtnStyle(running: boolean): React.CSSProperties {
  return { padding: '5px 10px', borderRadius: 5, border: '1px solid #ddd', background: '#fff', cursor: running ? 'pointer' : 'not-allowed', fontSize: 12, color: running ? '#333' : '#ccc' }
}

function tabBtnStyle(active: boolean): React.CSSProperties {
  return { padding: '4px 12px', borderRadius: 4, border: 'none', background: active ? '#1976d2' : 'transparent', color: active ? '#fff' : '#666', cursor: 'pointer', fontSize: 12 }
}

type Step = 1 | 2 | 3

const STEPS = [
  { n: 1, label: '打开网站', desc: '启动浏览器并导航到目标网站' },
  { n: 2, label: '开始任务', desc: '选择并开始一个审核任务' },
  { n: 3, label: '执行任务', desc: 'AI 审核并提交反馈' },
]

export default function BrowserPage() {
  const [running, setRunning] = useState(false)
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [customUrl, setCustomUrl] = useState('')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isXY = url.includes('xyzb.yuanfudao.com')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const [step, setStep] = useState<Step>(1)

  // Audit state
  const [taskCards, setTaskCards] = useState<string[]>([])
  const [selectedTask, setSelectedTask] = useState('')
  const [auditMessages, setAuditMessages] = useState<{ role: string; content: string; toolCalls?: any[] }[]>([])
  const [auditing, setAuditing] = useState(false)
  const [auditTab, setAuditTab] = useState<'screenshot' | 'audit' | 'logs'>('screenshot')
  const [rejectMode, setRejectMode] = useState(false)
  const [rejectCause, setRejectCause] = useState('')
  const [apiUrl, setApiUrl] = useState('')
  const [apiResult, setApiResult] = useState<string | null>(null)
  const [autoMode, setAutoMode] = useState(false)
  const [autoFetch, setAutoFetch] = useState(false)
  const [taskStarted, setTaskStarted] = useState(false)
  const [currentTaskName, setCurrentTaskName] = useState('')
  const [hoveredStep, setHoveredStep] = useState<number | null>(null)

  const addLog = useCallback((msg: string) => {
    const t = new Date().toLocaleTimeString()
    setLogs((prev) => [`${t} ${msg}`, ...prev].slice(0, 50))
  }, [])

  const pollStatus = useCallback(async () => {
    const status = await getBrowserStatus()
    setRunning(status.running)
    setUrl(status.url || '')
    setTitle(status.title || '')
    if (status.running) {
      const img = await getBrowserScreenshot()
      setScreenshot(img)
    } else {
      setScreenshot(null)
    }
  }, [])

  useEffect(() => {
    pollStatus()
    intervalRef.current = setInterval(pollStatus, 3000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [pollStatus])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [auditMessages])

  // Auto-fetch tasks when on xiaoyuan
  useEffect(() => {
    if (!isXY || !autoFetch) return
    handleGetTasks()
    const t = setInterval(handleGetTasks, 15000)
    return () => clearInterval(t)
  }, [isXY, autoFetch])

  // === Browser Handlers ===
  const handleStart = async () => {
    const res = await startBrowser()
    addLog(res.message || '启动中...')
    for (let i = 0; i < 10; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      const status = await getBrowserStatus()
      if (status.running) { setRunning(true); setUrl(status.url || ''); setTitle(status.title || ''); addLog('浏览器就绪'); return }
    }
    addLog('浏览器启动超时')
    pollStatus()
  }

  const handleStop = async () => {
    const res = await stopBrowser()
    addLog(res.message || '浏览器已关闭')
    pollStatus()
  }

  const callTool = async (name: string, args: any = {}) => {
    await fetch(`${API_BASE}/tools/execute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, args }),
    })
  }

  const handleNavigate = async (name: string) => {
    addLog(`正在打开 ${name}...`)
    await callTool('open_website_by_name', { name })
    addLog(`已打开 ${name}`)
    setTimeout(pollStatus, 1000)
  }

  const handleCustomUrl = async () => {
    if (!customUrl.trim()) return
    addLog(`正在打开 ${customUrl}...`)
    await callTool('open_custom_url', { url: customUrl })
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
        if (sorted.length > 0) setSelectedTask(sorted[0])
      } catch { setTaskCards([]) }
    }
  }

  const handleStartTask = async (name?: string) => {
    const taskName = name || selectedTask
    if (!taskName) return
    setCurrentTaskName(taskName)
    addLog(`开始任务: ${taskName}...`)
    const result = await executeTool('start_task', { card_title: taskName })
    setTaskStarted(true)
    addLog(result)
  }

  const handleGetQuestion = async () => {
    addLog('获取题目信息...')
    const result = await executeTool('get_question_info')
    addLog(result)
  }

  const handleAudit = async () => {
    setAuditing(true)
    setAuditTab('audit')
    setAuditMessages([{ role: 'assistant', content: '⏳ AI 正在审核中...' }])
    const systemPrompt = `你是一个小猿众包题目审核自动化助手。当前任务：单题标答-审核。操作流程：1. 先调用 scroll_canvas() 向下滚动查看完整题目。2. 然后调用 zoom_question() 缩小视图。3. 滚动/缩放后会更新截图。4. 调用 mark_question_correct() 处理判定。5. 说明你的判断结果。注意：不要提交或驳回任务，等待用户确认。`
    let assistantContent = ''
    streamChat(
      { model: 'doubao-seed-2-0-pro-260215', temperature: 0.1, prompt: '请审核这道题。', history: [], system_prompt: systemPrompt },
      (event) => {
        if (event.type === 'token') { assistantContent += event.data; setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { ...last[last.length - 1], content: assistantContent }; return last }) }
        else if (event.type === 'tool_start') { setAuditMessages((prev) => { const last = [...prev]; const calls = last[last.length - 1].toolCalls || []; calls.push({ name: event.data.name, status: 'running' }); last[last.length - 1] = { ...last[last.length - 1], toolCalls: [...calls] }; return last }); addLog(`工具: ${event.data.name}`) }
        else if (event.type === 'tool_end') { setAuditMessages((prev) => { const last = [...prev]; const calls = (last[last.length - 1].toolCalls || []).map((c: any) => c.name === event.data.name ? { ...c, status: 'done' } : c); last[last.length - 1] = { ...last[last.length - 1], toolCalls: calls }; return last }); addLog(`完成: ${event.data.name}`) }
        else if (event.type === 'error') { setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { ...last[last.length - 1], content: `❌ ${event.data}` }; return last }); setAuditing(false) }
      },
      (error) => { setAuditMessages((prev) => { const last = [...prev]; last[last.length - 1] = { role: 'assistant', content: `❌ ${error}` }; return last }); setAuditing(false) },
      () => { setAuditing(false); addLog('AI 审核完成') },
    )
  }

  const handleCorrect = async () => {
    addLog('标记正确...')
    await executeTool('mark_question_correct')
    await executeTool('submit_task', { action: '提交领下一任务' })
    addLog('完成')
    setTaskStarted(false)
    if (autoMode) autoContinue()
  }

  const handleSubmitReject = async (cause: string) => {
    addLog(`驳回: ${cause}...`)
    await executeTool('submit_task', { action: '整题驳回', reject_reason: cause })
    await executeTool('confirm_rejection')
    addLog('完成')
    setRejectMode(false); setRejectCause('')
    setTaskStarted(false)
    if (autoMode) autoContinue()
  }

  const autoContinue = async () => {
    addLog('自动获取下一任务...')
    const result = await executeTool('get_task_cards')
    const titles = result.split('\n').find((l: string) => l.includes('所有标题'))
    if (titles) {
      try {
        const str = (titles.split('：')[1] || '[]').replace(/'/g, '"')
        const arr = JSON.parse(str) as string[]
        if (arr.length > 0) {
          setSelectedTask(arr[0]); setCurrentTaskName(arr[0])
          await executeTool('start_task', { card_title: arr[0] })
          setTaskStarted(true); addLog(`自动开始: ${arr[0]}`)
          return
        }
      } catch {}
    }
    addLog('无可用任务')
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

  const resetStep = () => { setStep(1); setTaskStarted(false); setCurrentTaskName(''); setAuditMessages([]); setRejectMode(false) }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px 20px', gap: 12, boxSizing: 'border-box' }}>
      {/* Pipeline steps */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {STEPS.map((s) => {
          const active = step === s.n
          const done = s.n < step
          const showDesc = hoveredStep === s.n
          return (
            <div key={s.n} onClick={() => setStep(s.n as Step)}
              onMouseEnter={() => setHoveredStep(s.n)} onMouseLeave={() => setHoveredStep(null)}
              style={{
                flex: 1, padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
                background: active ? '#1976d2' : done ? '#e8f5e9' : '#f5f5f5',
                border: active ? '2px solid #1976d2' : done ? '2px solid #4caf50' : '2px solid #e0e0e0',
                transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 8,
                height: showDesc ? 48 : 32, overflow: 'hidden',
              }}
            >
              <span style={{
                width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                background: active ? '#fff' : done ? '#4caf50' : '#e0e0e0',
                color: active ? '#1976d2' : '#fff', fontWeight: 700, fontSize: 12,
              }}>{done ? '✓' : s.n}</span>
              <span style={{
                fontWeight: 600, fontSize: 13, color: active ? '#fff' : done ? '#2e7d32' : '#999',
                whiteSpace: 'nowrap',
              }}>{s.label}</span>
              {showDesc && (
                <span style={{
                  fontSize: 11, color: active ? 'rgba(255,255,255,0.8)' : done ? '#66bb6a' : '#bbb',
                  marginLeft: 4, whiteSpace: 'nowrap',
                }}>{s.desc}</span>
              )}
            </div>
          )
        })}
        <button onClick={resetStep} style={{
          padding: '4px 10px', borderRadius: 6, border: '1px solid #e0e0e0',
          background: '#fff', cursor: 'pointer', fontSize: 11, color: '#999', flexShrink: 0,
        }}>↺</button>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* Left panel */}
        <div style={{ width: 260, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>自动化控制</h2>

          {/* Step 1: 打开网站 */}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={handleStart} disabled={running} style={{
                  flex: 1, padding: '9px 0', borderRadius: 6, border: 'none',
                  background: running ? '#e0e0e0' : '#1976d2', color: running ? '#999' : '#fff',
                  cursor: running ? 'not-allowed' : 'pointer', fontSize: 14, fontWeight: 500,
                }}>{running ? '已启动' : '启动浏览器'}</button>
                <button onClick={handleStop} disabled={!running} style={{
                  flex: 1, padding: '9px 0', borderRadius: 6, border: '1px solid #ddd',
                  background: !running ? '#f5f5f5' : '#fff', color: !running ? '#ccc' : '#e53935',
                  cursor: !running ? 'not-allowed' : 'pointer', fontSize: 14,
                }}>关闭</button>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>快捷网址</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {WEBSITES.map((w) => (
                    <button key={w.name} onClick={() => handleNavigate(w.name)}
                      disabled={!running} style={{
                        padding: '5px 12px', borderRadius: 5, border: '1px solid #ddd',
                        background: '#fff', cursor: running ? 'pointer' : 'not-allowed',
                        fontSize: 12, color: running ? '#333' : '#ccc',
                      }}>{w.name}</button>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                <input value={customUrl} onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="网址..." disabled={!running}
                  onKeyDown={(e) => e.key === 'Enter' && handleCustomUrl()}
                  style={{ flex: 1, padding: '7px 10px', borderRadius: 5, border: '1px solid #ddd', fontSize: 12, outline: 'none' }} />
                <button onClick={handleCustomUrl} disabled={!running || !customUrl.trim()} style={{
                  padding: '7px 12px', borderRadius: 5, border: 'none',
                  background: !running || !customUrl.trim() ? '#e0e0e0' : '#1976d2', color: '#fff',
                  cursor: 'pointer', fontSize: 12,
                }}>打开</button>
              </div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                <button onClick={async () => { await callTool('refresh_page'); addLog('已刷新') }} disabled={!running} style={actionBtnStyle(running)}>🔄 刷新</button>
                <button onClick={async () => { await callTool('save_cookies'); addLog('Cookie 已保存') }} disabled={!running} style={actionBtnStyle(running)}>💾 保存Cookie</button>
                <button onClick={async () => { await callTool('load_cookies'); addLog('Cookie 已加载') }} disabled={!running} style={actionBtnStyle(running)}>📂 加载Cookie</button>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>网页请求</div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)}
                    placeholder="目标 URL..." style={{ flex: 1, padding: '5px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }}
                    onKeyDown={(e) => e.key === 'Enter' && handleApiRequest()} />
                  <button onClick={handleApiRequest} disabled={!apiUrl.trim()} style={{
                    padding: '5px 10px', borderRadius: 4, border: 'none',
                    background: !apiUrl.trim() ? '#e0e0e0' : '#1976d2', color: '#fff', cursor: 'pointer', fontSize: 12,
                  }}>请求</button>
                </div>
                {apiResult && <div style={{ padding: '6px 8px', background: '#f9f9f9', borderRadius: 4, fontSize: 11, color: '#333', maxHeight: 80, overflow: 'auto', whiteSpace: 'pre-wrap', border: '1px solid #eee', marginTop: 4 }}>{apiResult.length > 500 ? apiResult.slice(0, 500) + '...' : apiResult}</div>}
              </div>
            </div>
          )}

          {/* Step 2: 开始任务 */}
          {step === 2 && isXY && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#f5a623' }}>📋 任务列表</div>
              <button onClick={handleGetTasks} style={{ width: '100%', padding: '8px 0', borderRadius: 5, border: 'none', background: '#1976d2', color: '#fff', cursor: 'pointer', fontSize: 13 }}>刷新任务</button>
              {taskCards.length > 0 && (
                <div>
                  {taskCards.map((t) => (
                    <div key={t} onClick={() => handleStartTask(t)} style={{
                      padding: '6px 10px', borderRadius: 5, cursor: 'pointer', fontSize: 12,
                      background: selectedTask === t ? '#fff3e0' : '#f9f9f9',
                      border: selectedTask === t ? '1px solid #ffb74d' : '1px solid #eee',
                      marginBottom: 3, display: 'flex', alignItems: 'center', gap: 6,
                    }}
                      onMouseEnter={(e) => { if (selectedTask !== t) e.currentTarget.style.background = '#f0f0f0' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = selectedTask === t ? '#fff3e0' : '#f9f9f9' }}
                    >
                      <span style={{ fontSize: 11, color: selectedTask === t ? '#f5a623' : '#ccc' }}>▶</span>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: 执行任务 */}
          {step === 3 && taskStarted && currentTaskName.includes('单题标答-审核') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button onClick={handleGetQuestion} style={{ width: '100%', padding: '8px 0', borderRadius: 5, border: '1px solid #ddd', background: '#fff', cursor: 'pointer', fontSize: 13 }}>🖼 获取题目信息</button>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#666', cursor: 'pointer' }}>
                <input type="checkbox" checked={autoMode} onChange={(e) => setAutoMode(e.target.checked)} />
                完成后自动开始下一任务
              </label>
              <button onClick={handleAudit} disabled={auditing} style={{
                width: '100%', padding: '10px 0', borderRadius: 5, border: 'none',
                background: auditing ? '#ccc' : '#f5a623', color: '#fff',
                cursor: auditing ? 'not-allowed' : 'pointer', fontSize: 14, fontWeight: 600,
              }}>{auditing ? '审核中...' : '🤖 AI 审核'}</button>

              {!auditing && auditMessages.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button onClick={handleCorrect} style={{ padding: '8px 0', borderRadius: 5, border: 'none', background: '#4caf50', color: '#fff', cursor: 'pointer', fontSize: 13 }}>✅ 确认正确</button>
                  <button onClick={() => setRejectMode(!rejectMode)} style={{ padding: '8px 0', borderRadius: 5, border: '1px solid #e53935', background: '#fff', color: '#e53935', cursor: 'pointer', fontSize: 13 }}>❌ 纠正</button>
                  {rejectMode && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <input value={rejectCause} onChange={(e) => setRejectCause(e.target.value)} placeholder="驳回原因..." style={{ padding: '6px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }} />
                      <button onClick={() => handleSubmitReject(rejectCause)} disabled={!rejectCause.trim()} style={{ padding: '6px 0', borderRadius: 4, border: 'none', background: !rejectCause.trim() ? '#ccc' : '#e53935', color: '#fff', cursor: 'pointer', fontSize: 12 }}>提交驳回</button>
                    </div>
                  )}
                </div>
              )}

              <details style={{ marginTop: 4 }}>
                <summary style={{ fontSize: 12, color: '#999', cursor: 'pointer', padding: '4px 0' }}>🔧 高级操作</summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                  <button onClick={async () => { await executeTool('mark_question_correct'); addLog('已标记正确') }} style={opBtnStyle()}>审核正确</button>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <input id="rej" placeholder="错误原因..." style={{ flex: 1, padding: '5px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 11 }} />
                    <button onClick={async () => { const el = document.getElementById('rej') as HTMLInputElement; if (el?.value) { await executeTool('submit_task', { action: '整题驳回', reject_reason: el.value }); addLog(`驳回: ${el.value}`); el.value = '' } }} style={opBtnStyle()}>驳回</button>
                  </div>
                </div>
              </details>
            </div>
            )}
          </div>

        {/* Right panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#f9f9f9', borderRadius: 6, fontSize: 13, flexShrink: 0 }}>
            <StatusDot ok={running} />
            <span>{running ? '运行中' : '未启动'}</span>
            {url && <span style={{ color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{title || url}</span>}
            <div style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
              <button onClick={() => setAuditTab('screenshot')} style={tabBtnStyle(auditTab === 'screenshot')}>截图</button>
              <button onClick={() => setAuditTab('audit')} style={tabBtnStyle(auditTab === 'audit')}>AI自动化</button>
              <button onClick={() => setAuditTab('logs')} style={tabBtnStyle(auditTab === 'logs')}>日志</button>
            </div>
          </div>

          <div style={{ flex: 1, border: '1px solid #e0e0e0', borderRadius: 8, overflow: 'hidden', background: '#fafafa', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
            {auditTab === 'screenshot' && (
              screenshot ? (
                <img src={`data:image/png;base64,${screenshot}`} alt="截图" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
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
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#666', cursor: 'pointer', padding: '4px 0' }}>
          <input type="checkbox" checked={autoFetch} onChange={(e) => setAutoFetch(e.target.checked)} />
          自动刷新任务列表
        </label>
      </div>
    </div>
  )
}
