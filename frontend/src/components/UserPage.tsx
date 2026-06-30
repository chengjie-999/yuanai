export default function UserPage({ user, onLogout }: { user: any; onLogout: () => void }) {
  return (
    <div style={{ height: '100%', overflow: 'auto', background: 'var(--bg-secondary)', padding: '40px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 480, width: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{ padding: '32px', textAlign: 'center', borderBottom: '1px solid var(--border-light)' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: 'var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 12px', color: '#fff', fontSize: 24, fontWeight: 700,
            }}>
              {(user?.username || 'U')[0].toUpperCase()}
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 4px' }}>{user?.display_name || user?.username}</h2>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>@{user?.username}</span>
          </div>
          <div style={{ padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-light)', fontSize: 14 }}>
              <span style={{ color: 'var(--text-secondary)' }}>用户 ID</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500, fontFamily: 'monospace' }}>{user?.id}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-light)', fontSize: 14 }}>
              <span style={{ color: 'var(--text-secondary)' }}>角色</span>
              <span style={{
                color: user?.role === 'admin' ? 'var(--accent)' : 'var(--text-secondary)', fontWeight: 500,
                background: user?.role === 'admin' ? 'var(--accent-light)' : 'var(--bg-tertiary)',
                padding: '2px 10px', borderRadius: 4, fontSize: 12,
              }}>{user?.role === 'admin' ? '管理员' : '普通用户'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', fontSize: 14 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Agent 启动命令</span>
              <code style={{ fontSize: 12, color: 'var(--text-primary)', background: 'var(--bg-tertiary)', padding: '4px 8px', borderRadius: 4 }}>
                agent/main.py --agent-id {user?.id}
              </code>
            </div>
          </div>
        </div>
        <button onClick={onLogout} style={{
          width: '100%', padding: '12px 0', borderRadius: 10,
          border: '1px solid var(--border)', background: 'var(--bg-primary)',
          cursor: 'pointer', fontSize: 14, color: 'var(--text-secondary)',
        }}>退出登录</button>
      </div>
    </div>
  )
}
