/* 充值中心页（宿主）——充值流程在可复用组件 RechargePanel（2026-11-06 用户拍板
   「充值页面做成独立的，以后其他地方充值也可以复用」：欠费弹窗/定制服务下单
   等场景直接 <RechargePanel /> 挂载）。本页 = 账户额度卡 + RechargePanel。 */
import { useState, useEffect } from 'react'
import { API_BASE, authHeaders } from '../api'
import { useIsMobile } from '../hooks/useIsMobile'
import RechargePanel from './RechargePanel'

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
}

export default function BillingPage() {
  const isMobile = useIsMobile()
  const [cost, setCost] = useState<any>(null)

  useEffect(() => {
    fetch(`${API_BASE}/auth/cost`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null)).then(setCost).catch(() => {})
  }, [])

  const balance = cost ? cost.paid - cost.billed_total : 0
  const owe = balance < 0
  const fmt = (v: number) => (Math.abs(v) < 0.0001 ? '¥0.00' : `${v < 0 ? '-' : ''}¥${Math.abs(v) >= 0.01 ? Math.abs(v).toFixed(2) : String(Number(Math.abs(v).toPrecision(2)))}`)

  return (
    <div style={{ height: '100%', overflowY: 'auto', background: 'var(--bg-secondary)', padding: isMobile ? '16px 12px' : '28px 20px 40px', display: 'flex' }}>
      {/* margin auto 居中：flex justifyContent:center 内容溢出时上下裁剪滚不到底 */}
      <div style={{ maxWidth: 560, width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* 账户额度 */}
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

        {/* 可复用充值面板 */}
        <RechargePanel />
      </div>
    </div>
  )
}
