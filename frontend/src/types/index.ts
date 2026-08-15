export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  images?: string[]
  htmls?: string[]
  toolCalls?: ToolCall[]
  reasoning?: string
  reasoningTime?: number
  sender?: 'orchestrator' | 'analysis' | 'collection' | 'automation' | 'claude'
  pageLink?: string
  progress?: { current: number; total: number; message?: string }
}

export interface ToolCall {
  name: string
  status: 'running' | 'done' | 'error'
  result?: string
  duration?: number
}

export interface SSEEvent {
  type: 'token' | 'reasoning' | 'tool_start' | 'tool_end' | 'done' | 'error' | 'progress' | 'image' | 'html' | 'dashboard' | 'agent' | 'approval'
  data: any
}

export interface ToolInfo {
  name: string
  description: string
  args: Record<string, any>
  category: string
  admin_only?: boolean
}
