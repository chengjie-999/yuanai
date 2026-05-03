export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  images?: string[]
  toolCalls?: ToolCall[]
  reasoning?: string
}

export interface ToolCall {
  name: string
  status: 'running' | 'done' | 'error'
  result?: string
  duration?: number
}

export interface SSEEvent {
  type: 'token' | 'tool_start' | 'tool_end' | 'done' | 'error'
  data: any
}

export interface ToolInfo {
  name: string
  description: string
  args: Record<string, any>
}
