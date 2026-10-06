export const API_BASE = '/api/v1'

export function getToken(): string {
  return localStorage.getItem('token') || ''
}

const MODEL_KEY = 'selectedModel'
const DEFAULT_MODEL = 'deepseek-v4-flash'

export function getStoredModel(): string {
  return localStorage.getItem(MODEL_KEY) || DEFAULT_MODEL
}

export function setStoredModel(model: string) {
  localStorage.setItem(MODEL_KEY, model)
}

// ---- 推理强度（聊天框开关，localStorage 持久化） ----
const EFFORT_KEY = 'reasoningEffort'

export function getStoredEffort(): 'low' | 'high' {
  return localStorage.getItem(EFFORT_KEY) === 'high' ? 'high' : 'low'
}

export function setStoredEffort(effort: 'low' | 'high') {
  localStorage.setItem(EFFORT_KEY, effort)
}

const USER_KEY = 'currentUser'

export function getStoredUser(): any {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') }
  catch { return null }
}

export function setStoredUser(user: any) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(USER_KEY)
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

export function headers(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const t = localStorage.getItem('token')
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

export async function safeJson(res: Response): Promise<any> {
  const text = await res.text()
  try { return JSON.parse(text) }
  catch { return null }
}

// ---- Theme ----
export async function fetchTheme(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/auth/theme`, { headers: authHeaders() })
    if (!res.ok) return ''
    const data = await res.json()
    return data.theme || ''
  } catch { return '' }
}

export async function saveTheme(theme: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/theme`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ theme }),
    })
    return res.ok
  } catch { return false }
}

// ---- 长期记忆（设置页「我的记忆」卡） ----
export interface MemoryInfo {
  memory: string
  count: number
  max_items: number
  max_chars: number
}

export async function fetchMemory(): Promise<MemoryInfo> {
  try {
    const res = await fetch(`${API_BASE}/auth/memory`, { headers: authHeaders() })
    if (!res.ok) return { memory: '', count: 0, max_items: 100, max_chars: 2000 }
    const data = await res.json()
    return {
      memory: data.memory || '',
      count: data.count || 0,
      max_items: data.max_items || 100,
      max_chars: data.max_chars || 2000,
    }
  } catch { return { memory: '', count: 0, max_items: 100, max_chars: 2000 } }
}

export async function saveMemory(memory: string): Promise<{ ok: boolean; detail?: string; memory?: string; count?: number }> {
  try {
    const res = await fetch(`${API_BASE}/auth/memory`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ memory }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) return { ok: false, detail: (data as any).detail || '保存失败' }
    return { ok: true, memory: data.memory, count: data.count }
  } catch { return { ok: false, detail: '网络错误，请稍后重试' } }
}

// ---- Profile ----
export async function updateProfile(display_name: string) {
  const res = await fetch(`${API_BASE}/auth/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ display_name }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '更新失败')
  }
  return res.json()
}

export async function changePassword(old_password: string, new_password: string) {
  const res = await fetch(`${API_BASE}/auth/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ old_password, new_password }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '修改失败')
  }
  return res.json()
}

// ---- Models ----
export async function fetchModels(): Promise<Record<string, { label: string; provider: string }>> {
  try {
    const res = await fetch(`${API_BASE}/admin/models`, { headers: authHeaders() })
    if (!res.ok) return {}
    return await res.json()
  } catch { return {} }
}

// ---- API Keys ----
export async function fetchApiKeys(): Promise<Record<string, string>> {
  try {
    const res = await fetch(`${API_BASE}/auth/apikeys`, { headers: authHeaders() })
    if (!res.ok) return {}
    const data = await res.json()
    return data.keys || {}
  } catch { return {} }
}

export async function saveApiKey(provider: string, key: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/apikeys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ provider, key }),
    })
    return res.ok
  } catch { return false }
}

export async function deleteApiKey(provider: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/apikeys`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ provider, key: '' }),
    })
    return res.ok
  } catch { return false }
}

// ---- Agent Models ----
export async function fetchAgentModels(): Promise<Record<string, string>> {
  try {
    const res = await fetch(`${API_BASE}/auth/agent-models`, { headers: authHeaders() })
    if (!res.ok) return {}
    const data = await res.json()
    return data.agent_models || {}
  } catch { return {} }
}

export async function updateAgentModel(role: string, model_id: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/agent-models`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ role, model_id }),
    })
    return res.ok
  } catch { return false }
}

// ---- Agent Voices ----
export async function fetchAgentVoices(): Promise<Record<string, string>> {
  try {
    const res = await fetch(`${API_BASE}/auth/agent-voices`, { headers: authHeaders() })
    if (!res.ok) return {}
    const data = await res.json()
    return data.agent_voices || {}
  } catch { return {} }
}

export async function updateAgentVoice(role: string, voice_id: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/auth/agent-voices`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ role, voice_id }),
    })
    return res.ok
  } catch { return false }
}

// ---- Auth ----
export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '登录失败')
  }
  return res.json()
}

export async function register(username: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '注册失败')
  }
  return res.json()
}

export async function checkToken(): Promise<{ valid: boolean; user?: any; detail?: string }> {
  const token = getToken()
  if (!token) return { valid: false }
  try {
    const res = await fetch(`${API_BASE}/auth/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ token }),
    })
    if (!res.ok) {
      try { const err = await res.json(); return { valid: false, detail: err.detail || '登录已过期' } }
      catch { return { valid: false } }
    }
    return await res.json()
  } catch { return { valid: false } }
}

// ---- Tools ----
export async function fetchTools() {
  const res = await fetch(`${API_BASE}/tools/`, { headers: authHeaders() })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ---- Sessions ----
export async function createSession(title?: string): Promise<string> {
  const res = await fetch(`${API_BASE}/chat/session/new`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title: title || '新对话' }),
  })
  const data = await res.json()
  return data.session_id
}

export async function listSessions(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/chat/sessions`, { headers: authHeaders() })
    return await res.json()
  } catch { return [] }
}

export async function deleteSession(sessionId: string) {
  try {
    await fetch(`${API_BASE}/chat/session/${sessionId}`, { method: 'DELETE', headers: authHeaders() })
  } catch (e) { console.error('API 调用失败:', e) }
}

// ---- Messages ----
export async function loadMessages(sessionId: string): Promise<{ role: string; content: string; images?: string[] }[]> {
  try {
    const res = await fetch(`${API_BASE}/chat/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ session_id: sessionId }),
    })
    if (!res.ok) return []
    return await res.json()
  } catch { return [] }
}

export async function saveMessages(sessionId: string, messages: { role: string; content: string; images?: string[] }[], title?: string) {
  try {
    const body: any = { session_id: sessionId, messages }
    if (title) body.title = title
    await fetch(`${API_BASE}/chat/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })
  } catch (e) { console.error('API 调用失败:', e) }
}

// ---- Feedback ----
export type FeedbackState = { liked: boolean; disliked: boolean }

export async function loadFeedback(sessionId: string): Promise<Record<number, FeedbackState>> {
  try {
    const res = await fetch(`${API_BASE}/chat/feedback?session_id=${encodeURIComponent(sessionId)}`, { headers: authHeaders() })
    if (!res.ok) return {}
    const data = await res.json()
    const out: Record<number, FeedbackState> = {}
    if (data && typeof data === 'object') {
      for (const k of Object.keys(data)) {
        const v = data[k]
        out[Number(k)] = typeof v === 'object'
          ? { liked: !!v.liked, disliked: !!v.disliked }
          : { liked: !!v, disliked: false }   // 兼容旧服务端（bool 形状）
      }
    }
    return out
  } catch { return {} }
}

export async function setFeedback(sessionId: string, messageIndex: number,
  state: 'like' | 'dislike' | 'none'): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/chat/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        session_id: sessionId, message_index: messageIndex,
        liked: state === 'like', disliked: state === 'dislike',
      }),
    })
    return res.ok
  } catch { return false }
}

// ---- Stats ----
export async function trackVisit(path: string) {
  try {
    await fetch(`${API_BASE}/stats/visit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
  } catch { /* 埋点失败不影响体验 */ }
}

// ---- Voice ----
export interface VoiceCreds {
  app_id: string; room_id: string; user_id: string; rtc_token: string; task_id: string
}

export async function voiceStart(): Promise<VoiceCreds> {
  const res = await fetch(`${API_BASE}/voice/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: '{}',
  })
  if (!res.ok) {
    // 透出后端错误信息（503 未配置 / 502 RTC 调用失败）
    const data = await safeJson(res)
    throw new Error(data?.detail || `语音服务错误（${res.status}）`)
  }
  return await res.json()
}

export async function voiceEnd(roomId: string, taskId: string) {
  try {
    await fetch(`${API_BASE}/voice/end`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ room_id: roomId, task_id: taskId }),
    })
  } catch { /* 挂断尽力而为，失败不阻塞 UI */ }
}

export async function voiceMessage(sessionId: string, role: 'user' | 'assistant', content: string) {
  try {
    const res = await fetch(`${API_BASE}/voice/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ session_id: sessionId, role, content }),
    })
    if (!res.ok) console.warn('语音转录落库失败:', res.status)
  } catch { /* 转录持久化尽力而为 */ }
}

export async function voiceTts(text: string, sender?: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/voice/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text, sender }),
  })
  if (!res.ok) {
    const data = await safeJson(res)
    throw new Error(data?.detail || `语音合成错误（${res.status}）`)
  }
  return await res.blob()
}

// ---- Stream Chat ----
export function streamChat(
  params: {
    model: string
    temperature: number
    prompt: string
    images?: string[]
    history: { role: string; content: string }[]
    system_prompt: string
    session_id?: string
    decision?: { decision_id: string; approve: boolean }
    claude?: boolean
    force_cloud?: boolean
    reasoning_effort?: 'low' | 'high'
  },
  onEvent: (event: any) => void,
  onError: (error: string) => void,
  onDone: () => void,
  browserContext: boolean = false,
): AbortController {
  const controller = new AbortController()

  const url = params.claude
    ? `${API_BASE}/chat/claude-stream`
    : browserContext
      ? `${API_BASE}/chat/stream?browser_context=true`
      : `${API_BASE}/chat/stream`
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(params),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        // 提取后端错误详情（配额 429 等业务提示直接展示给用户）
        const text = await response.text()
        let msg = text
        try {
          const data = JSON.parse(text)
          if (data?.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        } catch { /* 非 JSON 用原文 */ }
        onError(msg)
        return
      }
      const reader = response.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              if (event.type === 'done') {
                onDone()
              } else {
                onEvent(event)
              }
            } catch { /* skip malformed SSE data */ }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(String(err))
      }
    })

  return controller
}

// ---- Stats ----
export async function fetchStats(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/stats/all`, { headers: authHeaders() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

// ---- Admin ----
export async function fetchWebsites(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/admin/websites`, { headers: authHeaders() })
    if (!res.ok) return []
    return await res.json()
  } catch { return [] }
}

export async function addWebsite(name: string, url: string, remark: string = ''): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/websites`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ name, url, remark }),
  })
  return res.json()
}

export async function deleteWebsite(id: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/admin/websites/${id}`, { method: 'DELETE', headers: authHeaders() })
    return res.ok
  } catch { return false }
}

export async function fetchFiles(path: string = ''): Promise<{ path: string; items: { name: string; path: string; is_dir: boolean; size_kb: number }[] }> {
  try {
    const res = await fetch(`${API_BASE}/admin/files?path=${encodeURIComponent(path)}`, { headers: authHeaders() })
    if (!res.ok) return { path, items: [] }
    return await res.json()
  } catch { return { path, items: [] } }
}

export async function freezeUser(userId: number, days: number): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/users/freeze`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ user_id: userId, days }),
  })
  return res.json()
}

export async function readFile(filePath: string): Promise<{ type: string; content?: string; data?: string; ext?: string; detail?: string }> {
  try {
    const res = await fetch(`${API_BASE}/admin/file/read?path=${encodeURIComponent(filePath)}`, { headers: authHeaders() })
    if (!res.ok) return { type: 'error', detail: '读取失败' }
    return await res.json()
  } catch { return { type: 'error', detail: '网络错误' } }
}

// ---- Crawl Records ----
export async function checkCrawlRecord(url: string): Promise<{ exists: boolean; id?: number; create_time?: string }> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/check?url=${encodeURIComponent(url)}`, { headers: authHeaders() })
    return await res.json()
  } catch { return { exists: false } }
}

export async function saveCrawlRecord(url: string, retype: string, result: string): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/record`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ url, retype, result }),
    })
    return await res.json()
  } catch { return { status: 'error' } }
}

export async function fetchCrawlRecords(page: number = 1, limit: number = 20): Promise<{ records: any[]; total: number; page: number }> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/records?page=${page}&limit=${limit}`, { headers: authHeaders() })
    if (!res.ok) return { records: [], total: 0, page: 1 }
    return await res.json()
  } catch { return { records: [], total: 0, page: 1 } }
}

export async function fetchCrawlRecordDetail(id: number): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/record/${id}`, { headers: authHeaders() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

export async function readCrawlRecordFile(id: number): Promise<{ type: string; content?: string; data?: string }> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/record/${id}/file`, { headers: authHeaders() })
    if (!res.ok) return { type: 'error' }
    return await res.json()
  } catch { return { type: 'error' } }
}

export async function deleteCrawlRecord(id: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/spider/save/record/${id}`, { method: 'DELETE', headers: authHeaders() })
    return res.ok
  } catch { return false }
}

// ---- Datasets ----
export async function uploadDataset(file: File): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await fetch(`${API_BASE}/data/upload`, {
      method: 'POST', headers: authHeaders(), body: form,
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'upload failed')
    return await res.json()
  } catch (e: any) { throw e }
}

export async function fetchDatasets(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/data/datasets`, { headers: authHeaders() })
    if (!res.ok) return []
    return await res.json()
  } catch { return [] }
}

export async function fetchDatasetPreview(id: number): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/data/dataset/${id}`, { headers: authHeaders() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

export async function deleteDataset(id: number): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/data/dataset/${id}`, { method: 'DELETE', headers: authHeaders() })
    return res.ok
  } catch { return false }
}

// ---- Code Monitor ----
export async function fetchMonitorStatus(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/monitor/status`, { headers: headers() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

export async function fetchMonitorChanges(limit: number = 50): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/monitor/changes?limit=${limit}`, { headers: headers() })
    if (!res.ok) return { changes: [], total: 0 }
    return await res.json()
  } catch { return { changes: [], total: 0 } }
}

export async function fetchMonitorTimeline(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/monitor/timeline`, { headers: headers() })
    if (!res.ok) return { timeline: [] }
    return await res.json()
  } catch { return { timeline: [] } }
}

/** 每日代码变更量（git 历史现算，重启不丢） */
export async function fetchMonitorDaily(days: number = 30): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/monitor/daily?days=${days}`, { headers: headers() })
    if (!res.ok) return []
    return (await res.json()).daily || []
  } catch { return [] }
}

export async function fetchMonitorFileTypes(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/monitor/file-types`, { headers: headers() })
    if (!res.ok) return { distributions: [] }
    return await res.json()
  } catch { return { distributions: [] } }
}

export async function fetchDatasetAnalysis(id: number, charts = false, force = false): Promise<any> {
  try {
    const params = new URLSearchParams()
    if (charts) params.set('charts', '1')
    if (force) params.set('force', '1')
    const qs = params.toString()
    const res = await fetch(`${API_BASE}/data/analyze/${id}${qs ? '?' + qs : ''}`, { headers: authHeaders() })
    if (!res.ok) return null
    return await res.json()
  } catch { return null }
}

