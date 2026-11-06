/* 充值面板（可复用组件，2026-11-06 用户拍板「充值页面做成独立的，其他地方充值也可以复用」）
   自包含：档位选择 → 创建订单（本地）→ 收款码 → 尾号备注 → 提交订单 →
   待确认（可取消）→ 充值记录（可点击查看订单详情）。
   复用点：BillingPage 充值中心 / 欠费提示弹窗 / 定制服务下单（后续接入时
   直接 <RechargePanel /> 挂载即可，零逻辑复制）。 */
import { useState, useEffect } from 'react'
import { API_BASE, authHeaders } from '../api'
import ZoomableImage from './chat/ZoomableImage'
import Modal from './Modal'

const AMOUNTS = [10, 50, 100]
const STATUS_LABEL: Record<string, { t: string; c: string }> = {
  created: { t: '待转账', c: 'var(--text-muted)' },
  pending: { t: '待确认', c: 'var(--warning)' },
  confirmed: { t: '已到账', c: 'var(--success)' },
  rejected: { t: '已驳回', c: 'var(--danger)' },
  cancelled: { t: '已取消', c: 'var(--text-muted)' },
}

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
  btn: { padding: '10px 22px', borderRadius: 8, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer' } as const,
}

export default function RechargePanel({ onSubmitted }: { onSubmitted?: (order: any) => void }) {
  const [amount, setAmount] = useState(50)
  // phase: pick 选金额 / qr 展示收款码填尾号 / submitted 已提交待确认
  const [phase, setPhase] = useState<'pick' | 'qr' | 'submitted'>('pick')
  const [order, setOrder] = useState<any>(null)
  const [tail, setTail] = useState('')
  const [note, setNote] = useState('')
  const [submitMsg, setSubmitMsg] = useState('')
  const [records, setRecords] = useState<any[]>([])
  const [qrOk, setQrOk] = useState(true)
  const [expandedQr, setExpandedQr] = useState(false)
  const [detail, setDetail] = useState<any>(null)

  const loadRecords = () => {
    fetch(`${API_BASE}/auth/payments`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setRecords(d?.records || []))
      .catch(() => {})
  }
  useEffect(() => { loadRecords() }, [])

  // 创建订单：仅前端本地状态（不落库）——提交成功才创建订单并发送管理员
  const createOrder = () => {
    setSubmitMsg('')
    setQrOk(true)
    setPhase('qr')
  }

  // 提交订单：此时才创建订单（pending）并发送管理员
  const submitOrder = async () => {
    if (!tail.trim() || tail.trim().length < 3) {
      setSubmitMsg('请填写转账账号尾号（用于管理员对账）')
      return
    }
    const res = await fetch(`${API_BASE}/auth/payments`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ amount, tail: tail.trim(), note }),
    })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) { setSubmitMsg(d.detail || '提交失败'); return }
    setOrder(d)
    setPhase('submitted')
    setSubmitMsg('')
    loadRecords()
    if (onSubmitted) onSubmitted(d)
  }

  const cancelOrder = async (pid: number, localOnly = false) => {
    if (localOnly) {
      setPhase('pick'); setTail(''); setNote(''); setOrder(null)
      return
    }
    if (!window.confirm('确定取消该订单？取消后会告知管理员。')) return
    try {
      const res = await fetch(`${API_BASE}/auth/payments/${pid}/cancel`, { method: 'POST', headers: authHeaders() })
      const d = await res.json().catch(() => ({}))
      if (!res.ok) { setSubmitMsg(d.detail || '取消失败'); return }
      setPhase('pick'); setTail(''); setNote(''); setOrder(null)
      setSubmitMsg('订单已取消（管理员可见）')
      loadRecords()
    } catch { setSubmitMsg('取消失败，请重试') }
  }

  const openDetail = async (pid: number) => {
    const res = await fetch(`${API_BASE}/auth/payments/${pid}`, { headers: authHeaders() })
    const d = await res.json().catch(() => ({}))
    setDetail(res.ok ? d : { error: d.detail || '加载失败' })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 充值卡 */}
      <div style={C.card}>
        <div style={C.title}>充值 <span style={C.sub}>— 微信/支付宝扫码转账，管理员确认后到账</span></div>
        <div style={{ padding: '16px 20px' }}>
          {phase === 'pick' && (
            <>
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
              <button onClick={createOrder} style={{ ...C.btn, width: '100%' }}>创建订单（¥{amount}）</button>
            </>
          )}

          {phase === 'qr' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                订单 ¥{amount} · 请使用微信/支付宝扫码转账
              </div>
              {qrOk ? (
                <div style={{ textAlign: 'center' }}>
                  <img src={`/api/v1/payment-qr?t=${Date.now()}`} alt="收款码"
                    onError={() => setQrOk(false)}
                    onClick={() => setExpandedQr(true)}
                    title="点击放大收款码" aria-label="点击放大收款码"
                    className="yuan-tip" data-tip="点击放大"
                    style={{ width: 200, maxWidth: '100%', height: 200, objectFit: 'contain',
                      borderRadius: 10, border: '1px solid var(--border)', background: '#fff',
                      cursor: 'zoom-in' }} />
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>点击收款码可放大</div>
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: 'var(--warning)', textAlign: 'center', padding: '12px' }}>
                  收款码尚未配置——请联系管理员上传（后台「设置 → 收款码」）
                </div>
              )}
              <input value={tail} onChange={(e) => setTail(e.target.value)} maxLength={20}
                placeholder="付款账号尾号（必填，如 8888）"
                style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
              <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={100}
                placeholder="补充备注（选填）"
                style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={submitOrder} style={{ ...C.btn, flex: 1 }}>提交订单</button>
                <button onClick={() => cancelOrder(0, true)}
                  style={{ padding: '10px 18px', borderRadius: 8, border: '1px solid var(--border)', background: 'none', color: 'var(--text-secondary)', fontSize: 14, cursor: 'pointer' }}>
                  取消
                </button>
              </div>
            </div>
          )}

          {phase === 'submitted' && order && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                订单号 <b style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>#{order.id}</b> · ¥{order.amount}
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, color: 'var(--warning)', background: 'var(--bg-tertiary)' }}>待确认</span>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.8 }}>
                已提交并通知管理员对账，确认后额度自动到账（通常几分钟内）。
                期间可取消订单（会告知管理员）；管理员确认后交易达成，不可取消。
              </div>
              <button onClick={() => cancelOrder(order.id)}
                style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'none', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer', alignSelf: 'flex-start' }}>
                取消订单
              </button>
            </div>
          )}

          {submitMsg && <div style={{ fontSize: 12.5, marginTop: 10, color: submitMsg.includes('失败') || submitMsg.includes('仅支持') ? 'var(--danger)' : 'var(--success)' }}>{submitMsg}</div>}
        </div>
      </div>

      {/* 充值记录（可点击查看订单详情） */}
      <div style={C.card}>
        <div style={C.title}>充值记录 <span style={C.sub}>— 点击可查看订单详情</span></div>
        {records.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', fontSize: 12.5, color: 'var(--text-muted)' }}>暂无记录</div>
        ) : records.map((r) => {
          const s = STATUS_LABEL[r.status] || STATUS_LABEL.confirmed
          return (
            <div key={r.id} onClick={() => openDetail(r.id)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 20px', borderBottom: '1px solid var(--border-light)', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-tertiary)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>¥{r.amount.toFixed(2)}</span>
              <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, color: s.c, background: 'var(--bg-tertiary)' }}>{s.t}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.note}>{r.note || ''}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11.5 }}>{r.created_at?.slice(5, 16)}</span>
            </div>
          )
        })}
      </div>

      {/* 收款码放大（聊天图片同款 ZoomViewport 缩放） */}
      {expandedQr && (
        <ZoomableImage src={`/api/v1/payment-qr?t=${Date.now()}`} onClose={() => setExpandedQr(false)} />
      )}

      {/* 订单详情 */}
      <Modal open={!!detail} title="订单详情" onClose={() => setDetail(null)} width={420}>
        {detail && !detail.error ? (
          <div style={{ padding: '8px 4px', fontSize: 13, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>订单号</span>
              <b style={{ fontFamily: 'monospace', color: 'var(--accent)' }}>#{detail.id}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>金额</span>
              <b style={{ color: 'var(--text-primary)' }}>¥{detail.amount.toFixed(2)}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-muted)' }}>状态</span>
              <span style={{ fontSize: 11, padding: '2px 10px', borderRadius: 999, color: (STATUS_LABEL[detail.status] || STATUS_LABEL.confirmed).c, background: 'var(--bg-tertiary)' }}>
                {(STATUS_LABEL[detail.status] || STATUS_LABEL.confirmed).t}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>创建时间</span>
              <span style={{ color: 'var(--text-secondary)' }}>{detail.created_at}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>转账信息</span>
              <span style={{ color: 'var(--text-secondary)', textAlign: 'right' }}>{detail.note || '—'}</span>
            </div>
          </div>
        ) : (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--danger)', fontSize: 13 }}>{detail?.error || '加载失败'}</div>
        )}
      </Modal>
    </div>
  )
}
