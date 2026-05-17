// Browser + workflow state types for BrowserPage

import type { Step } from './helpers'

export interface BrowserState {
  running: boolean
  url: string
  screenshot: string | null
  liveMode: boolean
  streamInterval: number
  browserBusy: boolean
  auditTab: 'screenshot' | 'audit' | 'logs'
}

export interface WorkflowState {
  step: Step
  taskCards: string[]
  selectedTask: string
  taskStarted: boolean
  currentTaskName: string
  startingTask: string
  taskFailCount: number
  questionImages: { type: string; data: string }[]
  expandedImage: string | null
  auditMessages: { role: string; content: string; toolCalls?: any[]; images?: string[] }[]
  auditing: boolean
  rejectMode: boolean
  rejectCause: string
  rejectNotes: string
  auditInput: string
}

export type BrowserAction =
  | { type: 'SET_RUNNING'; payload: boolean }
  | { type: 'SET_URL'; payload: string }
  | { type: 'SET_SCREENSHOT'; payload: string | null }
  | { type: 'SET_LIVE_MODE'; payload: boolean }
  | { type: 'SET_STREAM_INTERVAL'; payload: number }
  | { type: 'SET_BROWSER_BUSY'; payload: boolean }
  | { type: 'SET_AUDIT_TAB'; payload: 'screenshot' | 'audit' | 'logs' }

export function browserReducer(state: BrowserState, action: BrowserAction): BrowserState {
  switch (action.type) {
    case 'SET_RUNNING': return { ...state, running: action.payload }
    case 'SET_URL': return { ...state, url: action.payload }
    case 'SET_SCREENSHOT': return { ...state, screenshot: action.payload }
    case 'SET_LIVE_MODE': return { ...state, liveMode: action.payload }
    case 'SET_STREAM_INTERVAL': return { ...state, streamInterval: action.payload }
    case 'SET_BROWSER_BUSY': return { ...state, browserBusy: action.payload }
    case 'SET_AUDIT_TAB': return { ...state, auditTab: action.payload }
    default: return state
  }
}

export type WorkflowAction =
  | { type: 'SET_STEP'; payload: number }
  | { type: 'SET_TASK_CARDS'; payload: string[] }
  | { type: 'SET_SELECTED_TASK'; payload: string }
  | { type: 'SET_TASK_STARTED'; payload: boolean }
  | { type: 'SET_CURRENT_TASK_NAME'; payload: string }
  | { type: 'SET_STARTING_TASK'; payload: string }
  | { type: 'SET_TASK_FAIL_COUNT'; payload: number }
  | { type: 'INCREMENT_TASK_FAIL' }
  | { type: 'SET_QUESTION_IMAGES'; payload: { type: string; data: string }[] }
  | { type: 'SET_EXPANDED_IMAGE'; payload: string | null }
  | { type: 'SET_AUDIT_MESSAGES'; payload: { role: string; content: string; toolCalls?: any[]; images?: string[] }[] }
  | { type: 'ADD_AUDIT_MESSAGE'; payload: { role: string; content: string; toolCalls?: any[]; images?: string[] } }
  | { type: 'UPDATE_LAST_AUDIT_MESSAGE'; payload: Partial<{ role: string; content: string; toolCalls: any[]; images: string[] }> }
  | { type: 'APPEND_TOOL_CALL'; payload: { name: string } }
  | { type: 'MARK_TOOL_CALL_DONE'; payload: string }
  | { type: 'SET_AUDITING'; payload: boolean }
  | { type: 'SET_REJECT_MODE'; payload: boolean }
  | { type: 'SET_REJECT_CAUSE'; payload: string }
  | { type: 'SET_REJECT_NOTES'; payload: string }
  | { type: 'SET_AUDIT_INPUT'; payload: string }
  | { type: 'RESET_WORKFLOW' }

export function workflowReducer(state: WorkflowState, action: WorkflowAction): WorkflowState {
  switch (action.type) {
    case 'SET_STEP': return { ...state, step: action.payload }
    case 'SET_TASK_CARDS': return { ...state, taskCards: action.payload }
    case 'SET_SELECTED_TASK': return { ...state, selectedTask: action.payload }
    case 'SET_TASK_STARTED': return { ...state, taskStarted: action.payload }
    case 'SET_CURRENT_TASK_NAME': return { ...state, currentTaskName: action.payload }
    case 'SET_STARTING_TASK': return { ...state, startingTask: action.payload }
    case 'SET_TASK_FAIL_COUNT': return { ...state, taskFailCount: action.payload }
    case 'INCREMENT_TASK_FAIL': return { ...state, taskFailCount: state.taskFailCount + 1 }
    case 'SET_QUESTION_IMAGES': return { ...state, questionImages: action.payload }
    case 'SET_EXPANDED_IMAGE': return { ...state, expandedImage: action.payload }
    case 'SET_AUDIT_MESSAGES': return { ...state, auditMessages: action.payload }
    case 'ADD_AUDIT_MESSAGE': return { ...state, auditMessages: [...state.auditMessages, action.payload] }
    case 'UPDATE_LAST_AUDIT_MESSAGE': {
      const msgs = [...state.auditMessages]
      const last = { ...msgs[msgs.length - 1], ...action.payload }
      msgs[msgs.length - 1] = last
      return { ...state, auditMessages: msgs }
    }
    case 'APPEND_TOOL_CALL': {
      const msgs = [...state.auditMessages]
      const last = { ...msgs[msgs.length - 1] }
      last.toolCalls = [...(last.toolCalls || []), { name: action.payload.name, status: 'running' }]
      msgs[msgs.length - 1] = last
      return { ...state, auditMessages: msgs }
    }
    case 'MARK_TOOL_CALL_DONE': {
      const msgs = [...state.auditMessages]
      const last = { ...msgs[msgs.length - 1] }
      last.toolCalls = (last.toolCalls || []).map((tc: any) =>
        tc.name === action.payload ? { ...tc, status: 'done' } : tc
      )
      msgs[msgs.length - 1] = last
      return { ...state, auditMessages: msgs }
    }
    case 'SET_AUDITING': return { ...state, auditing: action.payload }
    case 'SET_REJECT_MODE': return { ...state, rejectMode: action.payload }
    case 'SET_REJECT_CAUSE': return { ...state, rejectCause: action.payload }
    case 'SET_REJECT_NOTES': return { ...state, rejectNotes: action.payload }
    case 'SET_AUDIT_INPUT': return { ...state, auditInput: action.payload }
    case 'RESET_WORKFLOW':
      return { ...state, step: 1, taskStarted: false, currentTaskName: '', auditMessages: [], rejectMode: false, rejectCause: '格式问题占比较多', rejectNotes: '', taskFailCount: 0, questionImages: [], expandedImage: null, auditInput: '' }
    default: return state
  }
}

export const initialBrowserState: BrowserState = {
  running: false,
  url: '',
  screenshot: null,
  liveMode: true,
  streamInterval: 100,
  browserBusy: false,
  auditTab: 'screenshot',
}

function _restore(key: string, fallback: any) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback } catch { return fallback }
}

export const initialWorkflowState: WorkflowState = {
  step: _restore('xy_step', 1),
  taskCards: _restore('xy_cards', []),
  selectedTask: _restore('xy_selected_task', ''),
  taskStarted: _restore('xy_task_started', false),
  currentTaskName: _restore('xy_current_task_name', ''),
  startingTask: '',
  taskFailCount: _restore('xy_task_fail_count', 0),
  questionImages: [],
  expandedImage: null,
  auditMessages: [],
  auditing: false,
  rejectMode: false,
  rejectCause: '格式问题占比较多',
  rejectNotes: '',
  auditInput: '',
}
