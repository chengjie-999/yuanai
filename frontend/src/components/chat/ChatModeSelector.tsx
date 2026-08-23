/* ============================================================
   聊天模式选择器 — 输入框（InputArea）与欢迎页（WelcomePage）共享
   三模式：云端（直连 LLM）/ 本地 Agent（本机统筹）/ Claude Code（本机桥接）
   本地 Agent 与 Claude Code 离线时置灰不可选
   ============================================================ */

export type ChatMode = 'local' | 'cloud' | 'claude'

export default function ChatModeSelector({ chatMode, setChatMode, localOnline, claudeOnline }: {
  chatMode: ChatMode
  setChatMode: (v: ChatMode) => void
  localOnline: boolean
  claudeOnline: boolean
}) {
  const options = [
    { key: 'cloud' as ChatMode, label: '云端', color: '#1976d2', online: true, tip: '云端模式：直接调用云端模型（跳过本地 Agent）' },
    { key: 'local' as ChatMode, label: '本地 Agent', color: '#2e7d32', online: localOnline, tip: localOnline ? '本地模式：对话交给本机统筹 Agent（多智能体委派）' : '本地 Agent 离线，暂不可选' },
    { key: 'claude' as ChatMode, label: '⌘ Claude Code', color: '#d97757', online: claudeOnline, tip: claudeOnline ? 'Claude Code 模式：对话直接发送到本机 Claude Code' : 'Claude Code 桥接离线，暂不可选' },
  ]

  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
      {options.map((o) => {
        const disabled = !o.online
        const active = chatMode === o.key
        return (
          <button key={o.key} onClick={() => { if (!disabled) setChatMode(o.key) }} disabled={disabled}
            title={o.tip}
            style={{
              background: active ? o.color : 'var(--bg-tertiary)',
              border: `1px solid ${active ? o.color : 'var(--border)'}`,
              color: active ? '#fff' : disabled ? 'var(--text-muted)' : 'var(--text-secondary)',
              cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 12, padding: '3px 10px', borderRadius: 20,
              fontWeight: 600, transition: 'all 0.15s',
              opacity: disabled && !active ? 0.55 : 1,
              display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            {/* 在线状态小圆点（云端恒亮） */}
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: active ? 'rgba(255,255,255,0.85)' : disabled ? 'var(--text-muted)' : '#4caf50',
              display: 'inline-block', flexShrink: 0,
            }} />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
