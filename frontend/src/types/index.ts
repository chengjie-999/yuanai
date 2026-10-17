/** 消息类型（信封协议；META 短键 ty，落库列 type） */
export type MsgType = 'chat' | 'tool_call' | 'tool_result' | 'summary' | 'note'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  images?: string[]
  htmls?: string[]
  toolCalls?: ToolCall[]
  reasoning?: string
  reasoningTime?: number
  sender?: 'orchestrator' | 'local' | 'analysis' | 'collection' | 'automation' | 'claude' | 'planet' | 'plan' | 'user'
  // 信封字段（多智能体群聊身份协议；META 短键 rp/tn/ty，与后端 message.py 对偶）
  recipient?: string        // "" = 广播；否则定向（@agent）
  turn?: number             // 1-based 轮次
  msgType?: MsgType         // 避免与 DOM/TS 的 type 概念冲突，字段名用 msgType
  pageLink?: string
  progress?: { current: number; total: number; message?: string }
  error?: string    // 流式错误（气泡错误卡 + 重试入口；META 短键 e）
  stopped?: boolean // 用户手动停止生成（META 短键 sp）
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
