import { useState, useEffect } from 'react'
import { Spinner, Empty, ErrorMsg, Card, btnPrimary, inputStyle, headers, API_BASE, badge } from './shared'
import Modal from '../Modal'

/* 举报工单（C7 投诉举报机制，2026-10-29）：用户气泡举报 → 管理员处理闭环 */
export default function ReportsTab() {
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')          // ''=全部 pending/handled
  const [handleId, setHandleId] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setError('')
    setLoading(true)
    const q = status ? `?status=${status}` : ''
    fetch(`${API_BASE}/admin/reports${q}`, { headers: headers() })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => { if (Array.isArray(d)) setReports(d) })
      .catch((e) => setError(`加载举报工单失败: ${e.message}`))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [status])

  const submitHandle = async () => {
    if (handleId === null || submitting) return
    setSubmitting(true)
    const res = await fetch(`${API_BASE}/admin/reports/${handleId}/handle`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...headers() },
      body: JSON.stringify({ note }),
    })
    setSubmitting(false)
    if (res.ok) { setHandleId(null); setNote(''); load() }
  }

  const filterChips = [
    { key: '', label: '全部' },
    { key: 'pending', label: '待处理' },
    { key: 'handled', label: '已处理' },
  ]

  return (
    <>
      {error && <ErrorMsg msg={error} onRetry={load} />}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        {filterChips.map((c) => (
          <button key={c.key} onClick={() => setStatus(c.key)}
            style={{
              padding: '5px 14px', borderRadius: 999, fontSize: 12, cursor: 'pointer',
              border: status === c.key ? '1px solid var(--accent)' : '1px solid var(--border)',
              background: status === c.key ? 'var(--accent-light)' : 'var(--bg-input)',
              color: status === c.key ? 'var(--accent)' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}>{c.label}</button>
        ))}
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              {['ID', '用户', '会话', '消息序号', '举报原因', '内容预览', '状态', '提交时间', '处理备注', '操作'].map((h) => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600, borderBottom: '2px solid var(--border)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {reports.length === 0 && <tr><td colSpan={10}><Empty msg="暂无举报工单" /></td></tr>}
              {reports.map((r) => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{r.id}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-primary)' }}>#{r.user_id}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.session_id}>{r.session_id.slice(0, 10)}...</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{r.message_index}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-primary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.content_preview}>{r.content_preview}</td>
                  <td style={{ padding: '10px 14px' }}>
                    {r.status === 'handled' ? badge('已处理', 'var(--success)') : badge('待处理', 'var(--warning)')}
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontSize: 12 }}>{r.created_at?.slice(0, 16)}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.handler_note}>{r.handler_note || (r.handled_at ? r.handled_at.slice(0, 16) : '—')}</td>
                  <td style={{ padding: '10px 14px' }}>
                    {r.status !== 'handled' && (
                      <button onClick={() => { setHandleId(r.id); setNote('') }} title="处理" aria-label="处理" style={btnPrimary}>处理</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {handleId !== null && (
        <Modal open title={`处理举报 #${handleId}`} onClose={() => { if (!submitting) setHandleId(null) }}>
          <div style={{ minWidth: 340 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>处理备注（留档）</div>
            <textarea value={note} onChange={(e) => setNote(e.target.value.slice(0, 500))}
              placeholder="如：已下架违规内容 / 已核实为误报"
              rows={3}
              style={{ ...inputStyle, width: '100%', resize: 'vertical' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
              <button onClick={() => setHandleId(null)} disabled={submitting}
                style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 16px', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)' }}>
                取消
              </button>
              <button onClick={submitHandle} disabled={submitting}
                style={{ ...btnPrimary, opacity: submitting ? 0.55 : 1, cursor: submitting ? 'default' : 'pointer' }}>
                {submitting ? '处理中...' : '确认处理'}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
