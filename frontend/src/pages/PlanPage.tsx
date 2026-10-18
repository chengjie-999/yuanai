import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { listPlans, getPlan, executePlan, deletePlan } from '../api/plan'
import type { Plan, PlanStep } from '../api/plan'
import { ArrowLeftIcon, ClipboardIcon, TrashIcon, AlertIcon, CheckIcon, LoaderIcon, XIcon, LinkIcon } from '../components/icons'
import { renderBody } from '../components/analysis/ResultBlocks'
import { AGENT_CONFIG } from '../config/agents'
import { timeAgo } from '../components/chat/helpers'
import { PLAN_MSG } from '../components/chat/planWindow'

/* ============================================================
   计划中心 /chat/plan — 手机定计划、电脑执行的第二段（队列与进度）
   - 列表 15s 轮询；详情执行中 3s 轮询、终态自停
   - 步骤时间线 + 进度条 + 结构化结果渲染（复用大屏 ResultBlocks）
   - 事件溯源执行记录（plan_runs）折叠展示
   ============================================================ */

const STATUS_CFG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: '草稿', color: 'var(--text-muted)', bg: 'var(--bg-secondary)' },
  queued: { label: '排队中', color: 'var(--accent)', bg: 'var(--accent-soft)' },
  running: { label: '执行中', color: 'var(--warning)', bg: 'var(--warning-soft)' },
  done: { label: '已完成', color: 'var(--success)', bg: 'var(--success-soft)' },
  failed: { label: '失败', color: 'var(--danger)', bg: 'var(--danger-soft)' },
}

const STEP_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待执行', color: 'var(--text-muted)' },
  running: { label: '运行中', color: 'var(--warning)' },
  done: { label: '已完成', color: 'var(--success)' },
  failed: { label: '失败', color: 'var(--danger)' },
  skipped: { label: '已跳过', color: 'var(--text-muted)' },
}

const RUN_EVENT_CN: Record<string, string> = {
  created: '计划创建', queued: '加入队列', claimed: '本机认领', progress: '进度更新',
  step_done: '步骤完成', step_failed: '步骤失败', step_retry: '自动重试',
  plan_done: '计划完成', plan_failed: '计划失败',
  watchdog_reset: '超时重置', step_reset: '重跑失败步骤',
}

function StatusChip({ status }: { status: string }) {
  const cfg = STATUS_CFG[status] || STATUS_CFG.draft
  return (
    <span style={{
      fontSize: 11, padding: '2px 10px', borderRadius: 999,
      color: cfg.color, background: cfg.bg, fontWeight: 600, whiteSpace: 'nowrap',
    }}>{cfg.label}</span>
  )
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div style={{ height: 4, borderRadius: 2, background: 'var(--bg-secondary)', overflow: 'hidden', flex: 1 }}>
      <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: 'var(--accent)', transition: 'width .4s' }} />
    </div>
  )
}

function StepIcon({ status }: { status: string }) {
  if (status === 'done') return <CheckIcon size={13} />
  if (status === 'failed') return <AlertIcon size={13} />
  if (status === 'running') return <LoaderIcon size={13} />
  return <span style={{ width: 7, height: 7, borderRadius: '50%', border: '1.5px solid currentColor', display: 'inline-block' }} />
}

export default function PlanPage({ onClose, hideBack }: { onClose?: () => void; hideBack?: boolean } = {}) {
  const [plans, setPlans] = useState<Plan[]>([])
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [detail, setDetail] = useState<Plan | null>(null)
  const [selectedId, setSelectedId] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [actionErr, setActionErr] = useState('')
  const [busy, setBusy] = useState(false)
  // 弹窗模式（独立窗口宿主）：opener 存在且非自身；一次性判定（opener 事后关闭不影响本次形态）
  const [isPopup] = useState(() => { try { return !!window.opener && window.opener !== window } catch { return false } })

  const refreshList = useCallback(async () => {
    try {
      setPlans(await listPlans())
      setErr('')
    } catch {
      setErr('计划列表加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshDetail = useCallback(async (pid: number) => {
    try {
      setDetail(await getPlan(pid))
    } catch { /* 保持旧数据 */ }
  }, [])

  // 列表轮询 15s
  useEffect(() => {
    refreshList()
    const t = setInterval(refreshList, 15000)
    return () => clearInterval(t)
  }, [refreshList])

  // 选中计划详情；执行中 3s 轮询、终态自停（照 usePlanetJob 自停模式）
  useEffect(() => {
    if (!selectedId) { setDetail(null); return }
    let t: any = null
    refreshDetail(selectedId)
    const active = detail?.status === 'queued' || detail?.status === 'running'
    if (active) t = setInterval(() => refreshDetail(selectedId), 3000)
    return () => { if (t) clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, detail?.status])

  // ---- 弹窗模式：父窗消息（refresh）与握手；用户手动开/关（AI 不自动关） ----
  useEffect(() => {
    if (!isPopup) return
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || e.data?.type !== PLAN_MSG) return
      if (e.data.action !== 'refresh') return
      refreshList()
      setSelectedId((cur) => (cur ? cur : -1))  // -1 = 待自动选中（列表加载后取第一条）
    }
    window.addEventListener('message', onMsg)
    try { window.opener?.postMessage({ type: PLAN_MSG, action: 'hello' }, window.location.origin) } catch { /* 忽略 */ }
    return () => window.removeEventListener('message', onMsg)
  }, [isPopup, refreshList])

  // -1 → 自动选中列表第一条（后端 id desc 排序 = 最新计划）
  useEffect(() => {
    if (selectedId === -1) setSelectedId(plans[0]?.id ?? 0)
  }, [selectedId, plans])

  const onExecute = async (p: Plan) => {
    setBusy(true); setActionErr('')
    try {
      const r = await executePlan(p.id)
      if (!r.agent_online) setActionErr('本机 Agent 未连接：计划已排队，电脑上线后自动开始')
      refreshDetail(p.id); refreshList()
    } catch {
      setActionErr('执行失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  const onRerunFailed = async (p: Plan) => {
    const failedIds = (p.steps || []).filter((s) => s.status === 'failed').map((s) => s.id)
    setBusy(true); setActionErr('')
    try {
      await executePlan(p.id, failedIds)
      refreshDetail(p.id); refreshList()
    } catch {
      setActionErr('重新执行失败，请稍后重试')
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (p: Plan) => {
    setBusy(true); setActionErr('')
    try {
      await deletePlan(p.id)
      if (selectedId === p.id) { setSelectedId(0); setDetail(null) }
      refreshList()
    } catch {
      setActionErr('删除失败（执行中的计划不能删除）')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="plan-page" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)', boxSizing: 'border-box' }}>
      <header style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        {isPopup ? (
          <button onClick={() => window.close()}
            className="yuan-tip yuan-tip-down" data-tip="关闭窗口" aria-label="关闭窗口"
            style={{
              fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
              padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
              flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
              background: 'transparent', cursor: 'pointer',
            }}><XIcon size={12} /> 关闭</button>
        ) : hideBack ? null : onClose ? (
          <button onClick={onClose} style={{
            fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
            padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
            flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
            background: 'transparent', cursor: 'pointer',
          }}><ArrowLeftIcon size={12} /> 返回对话</button>
        ) : (
          <Link to="/chat" style={{
            fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
            padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
            flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
          }}><ArrowLeftIcon size={12} /> 返回对话</Link>
        )}
        {/* 独立路由形态（浏览器直接打开）：与浮窗/浮层一致的浏览器式地址栏 */}
        {!isPopup && !hideBack && (
          <button onClick={() => {
            navigator.clipboard.writeText(window.location.href).then(() => {
              setCopiedUrl(true)
              setTimeout(() => setCopiedUrl(false), 1500)
            }).catch(() => {})
          }}
            className="yuan-tip" data-tip="点击复制此链接" title="复制页面链接" aria-label="复制页面链接"
            style={{
              flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 999, background: 'var(--bg-input)',
              border: '1px solid var(--border)', cursor: 'pointer', fontSize: 11,
              fontFamily: 'monospace', color: 'var(--text-secondary)',
              overflow: 'hidden', whiteSpace: 'nowrap',
            }}>
            {copiedUrl ? <CheckIcon size={11} style={{ flexShrink: 0 }} /> : <LinkIcon size={11} style={{ flexShrink: 0 }} />}
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{window.location.href}</span>
          </button>
        )}
        <span style={{ lineHeight: 1, color: 'var(--text-primary)', display: 'flex', flexShrink: 0 }}><ClipboardIcon size={18} /></span>
        <div style={{ flexShrink: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>计划</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>手机定计划，电脑执行</div>
        </div>
      </header>

      {actionErr && (
        <div style={{ margin: '10px 20px 0', padding: '8px 14px', borderRadius: 8, background: 'var(--danger-soft)', border: '1px solid var(--danger)', color: 'var(--danger)', fontSize: 12 }}>{actionErr}</div>
      )}

      <div className="plan-body agent-page-body" style={{ flex: 1, overflow: 'auto', maxWidth: 1080, width: '100%', margin: '0 auto', boxSizing: 'border-box', display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        {/* 计划列表 */}
        <div className="plan-list" style={{ flex: '0 0 320px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中…</div>
          ) : err ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>{err}</div>
          ) : plans.length === 0 ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.8 }}>
              还没有计划。在对话里说：
              <br />「帮我制定一个计划：先抓取 XX 的数据，
              <br />再做描述性统计分析和图表」
            </div>
          ) : (
            plans.map((p) => (
              <button key={p.id} onClick={() => setSelectedId(p.id)}
                style={{
                  textAlign: 'left', padding: '12px 14px', borderRadius: 10, cursor: 'pointer',
                  border: selectedId === p.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column', gap: 8,
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.title}</span>
                  <StatusChip status={p.status} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ProgressBar pct={p.progress} />
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{p.done_steps}/{p.total_steps}</span>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{timeAgo(p.update_time)}</span>
              </button>
            ))
          )}
        </div>

        {/* 详情 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!detail ? (
            <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
              <ClipboardIcon size={36} />
              <div style={{ marginTop: 10, fontSize: 13 }}>选择一个计划查看详情</div>
            </div>
          ) : (
            <PlanDetail plan={detail} busy={busy}
              onExecute={() => onExecute(detail)}
              onRerunFailed={() => onRerunFailed(detail)}
              onDelete={() => onDelete(detail)} />
          )}
        </div>
      </div>

      <style>{`
        @keyframes plan-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @media (max-width: 800px) {
          /* 内边距由全局 .agent-page-body 响应式规则统一（与项目其他页面一致） */
          .plan-body { flex-direction: column !important; }
          .plan-list { flex: none !important; width: 100% !important; }
        }
      `}</style>
    </div>
  )
}

function PlanDetail({ plan, busy, onExecute, onRerunFailed, onDelete }: {
  plan: Plan; busy: boolean
  onExecute: () => void; onRerunFailed: () => void; onDelete: () => void
}) {
  const steps = plan.steps || []
  const runs = plan.runs || []
  const hasFailed = steps.some((s) => s.status === 'failed')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 头部卡 */}
      <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 12, padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-primary)', flex: 1, minWidth: 0 }}>#{plan.id} {plan.title}</span>
          <StatusChip status={plan.status} />
        </div>
        {plan.goal && <div style={{ marginTop: 8, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{plan.goal}</div>}
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ProgressBar pct={plan.progress} />
          <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{plan.progress}%</span>
        </div>
        {plan.message && <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>{plan.message}</div>}
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {plan.status === 'draft' && (
            <button onClick={onExecute} disabled={busy}
              style={btnStyle()}>执行</button>
          )}
          {plan.status === 'failed' && hasFailed && (
            <button onClick={onRerunFailed} disabled={busy}
              style={btnStyle(true)}>重新执行失败步骤</button>
          )}
          {(plan.status === 'draft' || plan.status === 'done' || plan.status === 'failed') && (
            <button onClick={onDelete} disabled={busy} className="yuan-tip" data-tip="删除计划"
              style={{ ...btnStyle(), background: 'transparent', color: 'var(--danger)' }}>
              <TrashIcon size={14} /> 删除
            </button>
          )}
          {plan.status === 'queued' && !plan.agent_online && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', alignSelf: 'center' }}>等待本机 Agent 上线后自动开始</span>
          )}
        </div>
      </div>

      {/* 步骤时间线 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {steps.map((s) => <StepCard key={s.id} s={s} />)}
      </div>

      {/* 执行记录（事件溯源） */}
      {runs.length > 0 && (
        <details style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 12, padding: '10px 16px' }}>
          <summary style={{ cursor: 'pointer', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>执行记录（{runs.length} 条）</summary>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflow: 'auto' }}>
            {runs.map((r) => (
              <div key={r.id} style={{ display: 'flex', gap: 10, fontSize: 12, alignItems: 'baseline' }}>
                <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{r.create_time.slice(5, 16)}</span>
                <span style={{ color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{RUN_EVENT_CN[r.event] || r.event}</span>
                <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.message}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

function StepCard({ s }: { s: PlanStep }) {
  const st = STEP_STATUS[s.status] || STEP_STATUS.pending
  const skillCfg = AGENT_CONFIG[s.skill]
  const result = s.result
  return (
    <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 12, padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: st.color, border: `1.5px solid ${st.color}`,
          flexShrink: 0, animation: s.status === 'running' ? 'plan-spin 1.2s linear infinite' : 'none',
        }}><StepIcon status={s.status} /></span>
        <span style={{ fontSize: 11, fontWeight: 600, padding: '1px 8px', borderRadius: 6, color: skillCfg?.color || 'var(--text-muted)', background: skillCfg?.bg || 'var(--bg-secondary)' }}>{s.skill === 'analysis' ? '数据分析' : s.skill === 'collection' ? '数据采集' : s.skill}</span>
        {s.script && (
          <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 6, color: 'var(--text-secondary)', background: 'var(--bg-secondary)', whiteSpace: 'nowrap' }}>{s.script}</span>
        )}
        <span style={{ fontSize: 11, color: st.color, whiteSpace: 'nowrap' }}>{st.label}</span>
        <div style={{ flex: 1 }} />
        {s.attempt > 1 && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>第 {s.attempt} 次尝试</span>}
      </div>
      <div style={{ marginTop: 8, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>{s.desc}</div>
      {s.status === 'running' && (
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ProgressBar pct={s.progress} />
          <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{s.progress}%</span>
        </div>
      )}
      {s.status === 'running' && s.last_message && (
        <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>{s.last_message}</div>
      )}
      {s.status === 'failed' && s.error && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--danger)', lineHeight: 1.6 }}>{s.error}</div>
      )}
      {s.status === 'done' && result && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-light)' }}>
          {result.text ? (
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: 8 }}>
              {result.text.length > 2000 ? result.text.slice(0, 2000) + '…' : result.text}
            </div>
          ) : null}
          {result.blocks && typeof result.blocks === 'object' && !Array.isArray(result.blocks) && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>{renderBody(result.blocks)}</div>
          )}
          {result.truncated && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>结果过大已截断</div>}
          {result.script && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>执行脚本：{result.script}</div>}
        </div>
      )}
    </div>
  )
}

function btnStyle(accent = false) {
  return {
    fontSize: 12, padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
    border: '1px solid var(--accent)', background: accent ? 'var(--accent)' : 'transparent',
    color: accent ? '#fff' : 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: 4,
  }
}
