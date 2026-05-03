import type { ToolCall } from '../types'

function AnimatedDot() {
  return (
    <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
      <span style={{
        width: 4, height: 4, borderRadius: '50%', background: '#999',
        animation: 'pulse 1s ease-in-out infinite',
      }} />
      <span style={{
        width: 4, height: 4, borderRadius: '50%', background: '#999',
        animation: 'pulse 1s ease-in-out 0.2s infinite',
      }} />
      <span style={{
        width: 4, height: 4, borderRadius: '50%', background: '#999',
        animation: 'pulse 1s ease-in-out 0.4s infinite',
      }} />
    </span>
  )
}

const statusConfig = {
  running: { icon: '⚡', label: '运行中', dotColor: '#f5a623' },
  done: { icon: '✓', label: '完成', dotColor: '#4caf50' },
  error: { icon: '✕', label: '失败', dotColor: '#f44336' },
}

function ToolCallCard({ call }: { call: ToolCall }) {
  const cfg = statusConfig[call.status] || statusConfig.done

  return (
    <div style={{
      marginTop: 8,
      marginBottom: 4,
      borderRadius: 10,
      border: '1px solid #e5e5e5',
      overflow: 'hidden',
      fontSize: 13,
      background: '#fff',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        background: call.status === 'running' ? '#fffbe6' : '#fafafa',
      }}>
        <span style={{
          width: 20, height: 20, borderRadius: '50%',
          background: cfg.dotColor,
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 700,
          flexShrink: 0,
        }}>
          {cfg.icon}
        </span>
        <span style={{
          fontWeight: 600, color: '#333', fontSize: 13, flex: 1,
        }}>
          {call.name}
        </span>
        <span style={{
          fontSize: 12, color: cfg.dotColor, fontWeight: 500, flexShrink: 0,
        }}>
          {call.status === 'running' ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {cfg.label}<AnimatedDot />
            </span>
          ) : cfg.label}
        </span>
      </div>
      {call.status === 'done' && call.result && (
        <div style={{
          padding: '8px 12px',
          borderTop: '1px solid #f0f0f0',
          color: '#888',
          fontSize: 12,
          lineHeight: 1.5,
          maxHeight: 60,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {call.result.length > 120 ? call.result.slice(0, 120) + '...' : call.result}
        </div>
      )}
      {call.status === 'error' && (
        <div style={{
          padding: '8px 12px',
          borderTop: '1px solid #f0f0f0',
          color: '#f44336',
          fontSize: 12,
        }}>
          {call.result}
        </div>
      )}
    </div>
  )
}

export default ToolCallCard
