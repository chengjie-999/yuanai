import { useState, useEffect } from 'react'
import { API_BASE, getToken } from '../api'

export default function UserPage({ user }: { user: any }) {
  const [models, setModels] = useState<Record<string, any>>({})

  useEffect(() => {
    fetch(`${API_BASE}/admin/models`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    }).then((r) => r.json()).then(setModels).catch(() => {})
  }, [])

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#f8f9fb', padding: '40px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 480, width: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* 用户信息 */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', overflow: 'hidden' }}>
          <div style={{ padding: '32px', textAlign: 'center', borderBottom: '1px solid #f0f0f0' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: '#1976d2',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 12px', color: '#fff', fontSize: 24, fontWeight: 700,
            }}>
              {(user?.username || 'U')[0].toUpperCase()}
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: '#333', margin: '0 0 4px' }}>{user?.display_name || user?.username}</h2>
            <span style={{ fontSize: 13, color: '#999' }}>@{user?.username}</span>
          </div>
          <div style={{ padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f5f5f5', fontSize: 14 }}>
              <span style={{ color: '#999' }}>用户 ID</span>
              <span style={{ color: '#333', fontWeight: 500, fontFamily: 'monospace' }}>{user?.id}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #f5f5f5', fontSize: 14 }}>
              <span style={{ color: '#999' }}>角色</span>
              <span style={{
                color: user?.role === 'admin' ? '#1976d2' : '#666',
                fontWeight: 500,
                background: user?.role === 'admin' ? '#e3f2fd' : '#f5f5f5',
                padding: '2px 10px', borderRadius: 4, fontSize: 12,
              }}>{user?.role === 'admin' ? '管理员' : '普通用户'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', fontSize: 14 }}>
              <span style={{ color: '#999' }}>Agent 启动命令</span>
              <code style={{ fontSize: 12, color: '#666', background: '#f5f5f8', padding: '4px 8px', borderRadius: 4 }}>
                agent/main.py --agent-id {user?.id}
              </code>
            </div>
          </div>
        </div>

        {/* 模型配置 */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', overflow: 'hidden' }}>
          <div style={{ padding: '14px 24px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14, color: '#333', background: '#fafafa' }}>
            模型配置
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f5f5f8' }}>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>模型 ID</th>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>显示名</th>
                <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: '#666', fontWeight: 600 }}>供应商</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(models).map(([id, info]) => (
                <tr key={id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 12 }}>{id}</td>
                  <td style={{ padding: '10px 14px' }}>{info.label as string}</td>
                  <td style={{ padding: '10px 14px', color: '#666' }}>{info.provider as string}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 24px', fontSize: 11, color: '#999', background: '#fafafa' }}>
            model.py  File "config/settings.py" 中修改
          </div>
        </div>
      </div>
    </div>
  )
}
