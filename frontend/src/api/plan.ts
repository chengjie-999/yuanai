// 计划闭环 API（自包含模块，照 api/medical.ts 模式）
import { API_BASE, getToken } from './index'

const authHeaders = () => ({ Authorization: `Bearer ${getToken()}` })

export interface PlanStep {
  id: number; step_no: number; skill: string; script: string; desc: string
  params: Record<string, any>
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  attempt: number; progress: number; last_message: string; error: string
  claimed_at: string; started_at: string; finished_at: string
  result?: { text?: string; blocks?: any; truncated?: boolean; script?: string; summary?: string }
}

export interface PlanRun {
  id: number; step_id: number | null; event: string
  status_from: string; status_to: string; message: string
  payload: Record<string, any>; device_id: string; create_time: string
}

export interface Plan {
  id: number; title: string; goal: string
  status: 'draft' | 'queued' | 'running' | 'done' | 'failed'
  progress: number; total_steps: number; done_steps: number; failed_steps: number
  message: string; error: string
  create_time: string; update_time: string
  agent_online?: boolean
  steps?: PlanStep[]; runs?: PlanRun[]
}

export async function listPlans(): Promise<Plan[]> {
  const r = await fetch(`${API_BASE}/plan/list`, { headers: authHeaders() })
  if (!r.ok) throw new Error('HTTP ' + r.status)
  const d = await r.json()
  return d.plans || []
}

export async function getPlan(pid: number): Promise<Plan> {
  const r = await fetch(`${API_BASE}/plan/${pid}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(r.status === 404 ? 'NOT_FOUND' : 'HTTP ' + r.status)
  return r.json()
}

export async function executePlan(pid: number, stepIds: number[] = []): Promise<{ ok: boolean; already?: boolean; agent_online?: boolean }> {
  const r = await fetch(`${API_BASE}/plan/${pid}/execute`, {
    method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ step_ids: stepIds }),
  })
  if (!r.ok) throw new Error('HTTP ' + r.status)
  return r.json()
}

export async function deletePlan(pid: number): Promise<boolean> {
  const r = await fetch(`${API_BASE}/plan/${pid}`, { method: 'DELETE', headers: authHeaders() })
  if (!r.ok && r.status !== 409) throw new Error('HTTP ' + r.status)
  return r.ok
}
