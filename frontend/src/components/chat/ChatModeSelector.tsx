/* ============================================================
   聊天模式选择器 — 输入框（InputArea）与欢迎页（WelcomePage）共享
   三模式下拉：云端（直连 LLM）/ 本地 Agent（本机统筹）/ Claude Code（本机桥接）
   本地 Agent 与 Claude Code 离线时选项置灰不可选
   ============================================================ */

export type ChatMode = 'local' | 'cloud' | 'claude'

export default function ChatModeSelector({ chatMode, setChatMode, localOnline, claudeOnline }: {
  chatMode: ChatMode
  setChatMode: (v: ChatMode) => void
  localOnline: boolean
  claudeOnline: boolean
}) {
  const options = [
    { key: 'cloud' as ChatMode, label: '云端', online: true },
    { key: 'local' as ChatMode, label: '本地 Agent', online: localOnline },
    { key: 'claude' as ChatMode, label: '⌘ Claude Code', online: claudeOnline },
  ]

  return (
    <select
      value={chatMode}
      onChange={(e) => setChatMode(e.target.value as ChatMode)}
      title="聊天模式：选择由谁处理对话" aria-label="聊天模式"
      className="chat-mode-select"
      style={{
        background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 20,
        color: 'var(--text-primary)', fontSize: 12, fontWeight: 600,
        padding: '4px 26px 4px 12px', cursor: 'pointer', outline: 'none',
        appearance: 'none', WebkitAppearance: 'none',
        backgroundImage: 'linear-gradient(45deg, transparent 50%, var(--text-muted) 50%), linear-gradient(135deg, var(--text-muted) 50%, transparent 50%)',
        backgroundPosition: 'calc(100% - 14px) 55%, calc(100% - 10px) 55%',
        backgroundSize: '4px 4px, 4px 4px',
        backgroundRepeat: 'no-repeat',
      }}
    >
      {options.map((o) => (
        <option key={o.key} value={o.key} disabled={!o.online}
          style={{ background: 'var(--bg-primary)', color: o.online ? 'var(--text-primary)' : 'var(--text-muted)' }}>
          {o.label}{o.online ? '' : '（离线）'}
        </option>
      ))}
    </select>
  )
}
