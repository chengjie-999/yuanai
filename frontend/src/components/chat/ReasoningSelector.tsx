/* ============================================================
   推理强度选择器 — 与聊天模式选择器并列（输入区 / 欢迎页共享）
   快答（low）：省 token 响应快；深思（high）：复杂任务深度思考
   仅对 DeepSeek 系列生效（豆包由方舟接入点 thinking 控制；Claude 模式忽略）
   ============================================================ */

export type ReasoningEffort = 'low' | 'high'

export default function ReasoningSelector({ effort, setEffort }: {
  effort: ReasoningEffort
  setEffort: (v: ReasoningEffort) => void
}) {
  const options = [
    { key: 'low' as ReasoningEffort, label: '快答', tip: '快速回答：响应快、省额度（默认）' },
    { key: 'high' as ReasoningEffort, label: '深思', tip: '深度思考：复杂问题想得更透，响应更慢' },
  ]

  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      {options.map((o) => {
        const active = effort === o.key
        return (
          <button key={o.key} onClick={() => setEffort(o.key)}
            title={o.tip} className="yuan-tip" data-tip={o.tip} aria-label={o.tip}
            style={{
              background: active ? 'var(--accent)' : 'var(--bg-tertiary)',
              border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
              color: active ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: 12, padding: '3px 10px', borderRadius: 20,
              fontWeight: 600, transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: active ? 'rgba(255,255,255,0.85)' : 'var(--text-muted)',
              display: 'inline-block', flexShrink: 0,
            }} />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
