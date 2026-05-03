const API_BASE = '/api/v1'

// ---- Tools ----
export async function fetchTools() {
  const res = await fetch(`${API_BASE}/tools/`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ---- Sessions ----
export async function createSession(): Promise<string> {
  const res = await fetch(`${API_BASE}/chat/session/new`, { method: 'POST' })
  const data = await res.json()
  return data.session_id
}

export async function listSessions(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/chat/sessions`)
    return await res.json()
  } catch { return [] }
}

export async function deleteSession(sessionId: string) {
  try {
    await fetch(`${API_BASE}/chat/session/${sessionId}`, { method: 'DELETE' })
  } catch { /* ignore */ }
}

// ---- Messages ----
export async function loadMessages(sessionId: string): Promise<{ role: string; content: string }[]> {
  try {
    const res = await fetch(`${API_BASE}/chat/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
    if (!res.ok) return []
    return await res.json()
  } catch { return [] }
}

export async function saveMessages(sessionId: string, messages: { role: string; content: string }[]) {
  try {
    await fetch(`${API_BASE}/chat/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, messages }),
    })
  } catch { /* ignore */ }
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
): AbortController {
  const controller = new AbortController()

  fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
