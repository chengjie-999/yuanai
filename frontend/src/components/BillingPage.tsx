/* 充值页（盈利 MVP 2026-11-06）：个人收款码 + 订单登记人工确认——
   余额展示 / 收款码 / 档位选择 / 转账信息提交 / 充值记录 */
import { useState, useEffect } from 'react'
import { API_BASE, authHeaders } from '../api'
import { useIsMobile } from '../hooks/useIsMobile'

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
  btn: { padding: '10px 22px', borderRadius: 8, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer' } as const,
}

const AMOUNTS = [10, 50, 100]
const STATUS_LABEL: Record<string, { t: string; c: string }> = {
  pending: { t: '待确认', c: 'var(--warning)' },
  confirmed: { t: '已到账', c: 'var(--success)' },
  rejected: { t: '已驳回', c: 'var(--danger)' },
}

export default function BillingPage() {
  const isMobile = useIsMobile()
  const [cost, setCost] = useState<any>(null)
  const [amount, setAmount] = useState(50)
  const [order, setOrder] = useState<any>(null)
  const [note, setNote] = useState('')
  const [submitMsg, setSubmitMsg] = useState('')
  const [records, setRecords] = useState<any[]>([])
  const [qrOk, setQrOk] = useState(true)

  const load = () => {
    fetch(`${API_BASE}/auth/cost`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null)).then(setCost).catch(() => {})
    fetch(`${API_BASE}/auth/payments`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setRecords(d?.records || []))
      .catch(() => {})
  }
  useEffect(() => { load() }, [])

  const createOrder = async () => {
    setSubmitMsg('')
    const res = await fetch(`${API_BASE}/auth/payments`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ amount }),
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) { setSubmitMsg(d.detail || '创建订单失败'); return }
    setOrder(d)
    setQrOk(true)  // 管理员可能刚上传收款码——重新探测
    load()
  }

  const submitNote = async () => {
    if (!order) return
    const res = await fetch(`${API_BASE}/auth/payments/${order.id}/submit`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ note }),
    })
    const d = await res.json().catch(() => ({}))
    setSubmitMsg(res.ok ? (d.message || '已提交') : (d.detail || '提交失败'))
    if (res.ok) load()
  }

  const balance = cost ? cost.paid - cost.billed_total : 0
  const owe = balance < 0
  const fmt = (v: number) => (Math.abs(v) < 0.0001 ? '¥0.00' : `${v < 0 ? '-' : ''}¥${Math.abs(v) >= 0.01 ? Math.abs(v).toFixed(2) : String(Number(Math.abs(v).toPrecision(2)))}`)

  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--bg-secondary)', padding: isMobile ? '16px 12px' : '32px 20px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 560, width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 余额 */}
        <div style={C.card}>
          <div style={C.title}>账户额度</div>
          <div style={{ padding: '20px 24px', textAlign: 'center' }}>
            <div style={{ fontSize: 30, fontWeight: 800, color: owe ? 'var(--danger)' : 'var(--success)' }}>
              {cost ? fmt(balance) : '—'}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 6 }}>
              {owe
                ? `欠费（满 ¥${cost?.arrears_limit ?? 11} 将限制聊天）——充值后立即恢复`
                : '余额充足，消费按使用量自动扣减（计费价 = 成本 × 1.8）'}
            </div>
          </div>
        </div>

        {/* 充值 */}
        <div style={C.card}>
          <div style={C.title}>充值 <span style={C.sub}>— 微信/支付宝扫码转账，管理员确认后到账</span></div>
          <div style={{ padding: '16px 20px' }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              {AMOUNTS.map((a) => (
                <button key={a} onClick={() => setAmount(a)}
                  style={{ flex: 1, padding: '10px 0', borderRadius: 8, fontSize: 14, fontWeight: 700,
                    border: amount === a ? '2px solid var(--accent)' : '1px solid var(--border)',
                    background: amount === a ? 'var(--accent-soft)' : 'var(--bg-primary)',
                    color: amount === a ? 'var(--accent)' : 'var(--text-secondary)', cursor: 'pointer' }}>
                  ¥{a}
                </button>
              ))}
            </div>
            {!order ? (
              <button onClick={createOrder} style={{ ...C.btn, width: '100%' }}>生成充值订单（¥{amount}）</button>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  订单号 <b style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>#{order.id}</b> · ¥{order.amount} · 待确认
                </div>
                {qrOk ? (
                  <img src={`/api/v1/payment-qr?t=${order.id}`} alt="收款码"
                    onError={() => setQrOk(false)}
                    style={{ width: 180, height: 180, margin: '0 auto', borderRadius: 10, border: '1px solid var(--border)', background: '#fff' }} />
                ) : (
                  <div style={{ fontSize: 12.5, color: 'var(--warning)', textAlign: 'center', padding: '12px' }}>
                    收款码尚未配置——请联系管理员上传（后台「设置 → 收款码」）
                  </div>
                )}
                <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200}
                  placeholder="转账后填写：转账金额/时间/尾号（如：微信转 50 元 10:23 尾号8888）"
                  style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
                <button onClick={submitNote} style={{ ...C.btn }}>我已转账，提交确认</button>
              </div>
            )}
            {submitMsg && <div style={{ fontSize: 12.5, marginTop: 10, color: submitMsg.includes('失败') || submitMsg.includes('仅支持') ? 'var(--danger)' : 'var(--success)' }}>{submitMsg}</div>}
          </div>
        </div>

        {/* 充值记录 */}
        <div style={C.card}>
          <div style={C.title}>充值记录</div>
          {records.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 12.5, color: 'var(--text-muted)' }}>暂无记录</div>
          ) : records.map((r) => {
            const s = STATUS_LABEL[r.status] || STATUS_LABEL.confirmed
            return (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 20px', borderBottom: '1px solid var(--border-light)', fontSize: 13 }}>
                <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>¥{r.amount.toFixed(2)}</span>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, color: s.c, background: 'var(--bg-tertiary)' }}>{s.t}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 12, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.note || ''}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>{r.created_at?.slice(5, 16)}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
