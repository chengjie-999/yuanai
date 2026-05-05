import { WEBSITES, actionBtnStyle } from './helpers'

export default function Step1Content({ running, busy, customUrl, apiUrl, apiResult, onStart, onStop,
  onNavigate, onCustomUrl, setCustomUrl, onRefresh, onSaveCookies, onLoadCookies, onApiRequest, setApiUrl }: {
  running: boolean; busy?: boolean; customUrl: string; apiUrl: string; apiResult: string | null
  onStart: () => void; onStop: () => void; onNavigate: (name: string) => void
  onCustomUrl: () => void; setCustomUrl: (v: string) => void; onRefresh: () => void
  onSaveCookies: () => void; onLoadCookies: () => void; onApiRequest: () => void; setApiUrl: (v: string) => void
}) {
  const isBusy = busy || false
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 6 }}>
        <button className={`btn-click${isBusy ? ' btn-loading' : ''}`} onClick={onStart} disabled={running || isBusy} style={{
          flex: 1, padding: '9px 0', borderRadius: 6, border: 'none',
          background: running || isBusy ? '#e0e0e0' : '#1976d2', color: running || isBusy ? '#999' : '#fff',
          cursor: running || isBusy ? 'not-allowed' : 'pointer', fontSize: 14, fontWeight: 500,
        }}>{isBusy ? '启动中' : running ? '已启动' : '启动浏览器'}</button>
        <button className="btn-click" onClick={onStop} disabled={!running || isBusy} style={{
          flex: 1, padding: '9px 0', borderRadius: 6, border: '1px solid #ddd',
          background: !running || isBusy ? '#f5f5f5' : '#fff', color: !running || isBusy ? '#ccc' : '#e53935',
          cursor: !running || isBusy ? 'not-allowed' : 'pointer', fontSize: 14,
        }}>关闭</button>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>快捷网址</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {WEBSITES.map((w) => (
            <button key={w.name} className="btn-click" onClick={() => onNavigate(w.name)}
              disabled={!running} style={{
                padding: '5px 12px', borderRadius: 5, border: '1px solid #ddd',
                background: '#fff', cursor: running ? 'pointer' : 'not-allowed',
                fontSize: 12, color: running ? '#333' : '#ccc',
              }}>{w.name}</button>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 4 }}>
        <input value={customUrl} onChange={(e) => setCustomUrl(e.target.value)}
          placeholder="网址..." disabled={!running}
          onKeyDown={(e) => e.key === 'Enter' && onCustomUrl()}
          style={{ flex: 1, padding: '7px 10px', borderRadius: 5, border: '1px solid #ddd', fontSize: 12, outline: 'none' }} />
        <button className="btn-click" onClick={onCustomUrl} disabled={!running || !customUrl.trim()} style={{
          padding: '7px 12px', borderRadius: 5, border: 'none',
          background: !running || !customUrl.trim() ? '#e0e0e0' : '#1976d2', color: '#fff',
          cursor: 'pointer', fontSize: 12,
        }}>打开</button>
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        <button className="btn-click" onClick={onRefresh} disabled={!running} style={actionBtnStyle(running)}>🔄 刷新</button>
        <button className="btn-click" onClick={onSaveCookies} disabled={!running} style={actionBtnStyle(running)}>💾 保存Cookie</button>
        <button className="btn-click" onClick={onLoadCookies} disabled={!running} style={actionBtnStyle(running)}>📂 加载Cookie</button>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>网页请求</div>
        <div style={{ display: 'flex', gap: 4 }}>
          <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)}
            placeholder="目标 URL..." style={{ flex: 1, padding: '5px 8px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12 }}
            onKeyDown={(e) => e.key === 'Enter' && onApiRequest()} />
          <button className="btn-click" onClick={onApiRequest} disabled={!apiUrl.trim()} style={{
            padding: '5px 10px', borderRadius: 4, border: 'none',
            background: !apiUrl.trim() ? '#e0e0e0' : '#1976d2', color: '#fff', cursor: 'pointer', fontSize: 12,
          }}>请求</button>
        </div>
        {apiResult && <div style={{ padding: '6px 8px', background: '#f9f9f9', borderRadius: 4, fontSize: 11, color: '#333', maxHeight: 80, overflow: 'auto', whiteSpace: 'pre-wrap', border: '1px solid #eee', marginTop: 4 }}>{apiResult.length > 500 ? apiResult.slice(0, 500) + '...' : apiResult}</div>}
      </div>
    </div>
  )
}
