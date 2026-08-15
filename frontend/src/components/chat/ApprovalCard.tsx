import { useState, useEffect } from 'react'

interface Props {
  decisionId: string
  toolName: string
  command: string
  onDecision: (approve: boolean) => void
  timeoutSeconds?: number
}

/** Claude Code 桥接的待审批命令卡片：同意/拒绝（超时自动拒绝） */
export default function ApprovalCard({ decisionId, toolName, command, onDecision, timeoutSeconds = 120 }: Props) {
  const [remaining, setRemaining] = useState(timeoutSeconds)

  useEffect(() => {
    const t = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div style={{
      marginTop: 10, marginBottom: 14, borderRadius: 10,
      border: '1px solid #d97757', background: '#fdf6f0',
      padding: '10px 14px', fontSize: 13, maxWidth: 460,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontWeight: 600, color: '#d97757' }}>⌘ Claude Code 请求执行</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          工具: {toolName} · 审批ID: {decisionId.slice(0, 8)}
        </span>
      </div>
      <pre style={{
        margin: 0, padding: '8px 10px', borderRadius: 6,
        background: 'var(--bg-secondary)', whiteSpace: 'pre-wrap',
        wordBreak: 'break-all', fontSize: 12, maxHeight: 100, overflowY: 'auto',
      }}>{command}</pre>
      <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
        <button onClick={() => onDecision(true)}
          style={{
            padding: '6px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: '#4caf50', color: '#fff', fontWeight: 600, fontSize: 13,
          }}>✓ 同意执行</button>
        <button onClick={() => onDecision(false)}
          style={{
            padding: '6px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13,
            background: 'transparent', border: '1px solid var(--danger)', color: 'var(--danger)',
          }}>✕ 拒绝</button>
        <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 'auto' }}>
          {remaining > 0 ? `${remaining}s 后自动拒绝` : '已超时'}
        </span>
      </div>
    </div>
  )
}
