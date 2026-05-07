export const API_BASE = '/api/v1'

export function getToken(): string {
  return localStorage.getItem('token') || ''
}

const MODEL_KEY = 'selectedModel'
const DEFAULT_MODEL = 'doubao-seed-2-0-pro-260215'

export function getStoredModel(): string {
  return localStorage.getItem(MODEL_KEY) || DEFAULT_MODEL
}

export function setStoredModel(model: string) {
  localStorage.setItem(MODEL_KEY, model)
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
export async function createSession(): Promise<string> {
  const res = await fetch(`${API_BASE}/chat/session/new`, { method: 'POST', headers: authHeaders() })
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
  } catch { /* ignore */ }
}

// ---- Messages ----
export async function loadMessages(sessionId: string): Promise<{ role: string; content: string }[]> {
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

export async function saveMessages(sessionId: string, messages: { role: string; content: string }[], title?: string) {
  try {
    const body: any = { session_id: sessionId, messages }
    if (title) body.title = title
    await fetch(`${API_BASE}/chat/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })
  } catch { /* ignore */ }
}

// ---- Browser ----
export async function startBrowser() {
  const res = await fetch(`${API_BASE}/browser/start`, { method: 'POST', headers: authHeaders() })
  return res.json()
}

export async function stopBrowser() {
  const res = await fetch(`${API_BASE}/browser/stop`, { method: 'POST', headers: authHeaders() })
  return res.json()
}

export async function getBrowserStatus() {
  try {
    const res = await fetch(`${API_BASE}/browser/status`, { headers: authHeaders() })
    return await res.json()
  } catch { return { running: false, url: '', title: '' } }
}

export async function getBrowserScreenshot(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/browser/screenshot`, { headers: authHeaders() })
    if (!res.ok) return null
    const data = await res.json()
    return data.screenshot || null
  } catch { return null }
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
  },
  onEvent: (event: any) => void,
  onError: (error: string) => void,
  onDone: () => void,
  browserContext: boolean = false,
): AbortController {
  const controller = new AbortController()

  const url = browserContext
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
        onError(`HTTP ${response.status}: ${await response.text()}`)
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
            } catch { /* skip malformed */ }
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

// ---- Monitor (mss) ----
export async function getMonitorScreenshot(monitor: number = 0): Promise<{ status: string; screenshot?: string; width?: number; height?: number; detail?: string }> {
  try {
    const res = await fetch(`${API_BASE}/monitor/screenshot?monitor=${monitor}`, { headers: authHeaders() })
    return await res.json()
  } catch { return { status: 'error', detail: '网络请求失败' } }
}

export async function getMonitors(): Promise<{ status: string; monitors?: { monitor: number; width: number; height: number; label: string }[]; detail?: string }> {
  try {
    const res = await fetch(`${API_BASE}/monitor/monitors`, { headers: authHeaders() })
    return await res.json()
  } catch { return { status: 'error', detail: '网络请求失败' } }
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

// ---- Batch Crawl ----
export async function batchFetchUrls(params: {
  urls: string[]; retype?: string; method?: string; data?: any; cookie_site?: string
}): Promise<{ results: { url: string; status: string; preview?: string; detail?: string }[] }> {
  try {
    const res = await fetch(`${API_BASE}/spider/batch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(params),
    })
    if (!res.ok) return { results: [] }
    return await res.json()
  } catch { return { results: [] } }
}
