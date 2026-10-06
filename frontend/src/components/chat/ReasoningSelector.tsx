/* ============================================================
   推理强度选择器（进度条形式，三档） — 与聊天模式选择器并列
   快答（low）：省 token 响应快；标准（medium）：均衡；深思（high）：深度思考
   仅对 DeepSeek 系列生效（豆包由方舟接入点 thinking 控制；Claude 模式忽略）
   ============================================================ */

export type ReasoningEffort = 'low' | 'medium' | 'high'

const LEVELS: { key: ReasoningEffort; label: string; tip: string }[] = [
  { key: 'low', label: '快答', tip: '快速回答：响应快、省额度' },
  { key: 'medium', label: '标准', tip: '标准推理：速度与思考的均衡（默认）' },
  { key: 'high', label: '深思', tip: '深度思考：复杂问题想得更透，响应更慢' },
]

export default function ReasoningSelector({ effort, setEffort }: {
  effort: ReasoningEffort
  setEffort: (v: ReasoningEffort) => void
}) {
  const idx = LEVELS.findIndex((l) => l.key === effort)

  const labelStyle = (i: number): React.CSSProperties => ({
    fontSize: 11,
    color: i === idx ? 'var(--accent)' : 'var(--text-muted)',
    fontWeight: i === idx ? 600 : 400,
    transition: 'color 0.15s',
    whiteSpace: 'nowrap',
  })

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}
      title={LEVELS[idx].tip} aria-label="推理强度">
      <span style={labelStyle(0)}>快答</span>
      <input
        type="range"
        min={0} max={2} step={1}
        value={idx}
        onChange={(e) => setEffort(LEVELS[Number(e.target.value)].key)}
        aria-label="推理强度滑块（快答/标准/深思）"
        style={{ width: 64, accentColor: 'var(--accent)', cursor: 'pointer', margin: 0 }}
      />
      <span style={labelStyle(2)}>深思</span>
    </div>
  )
}
