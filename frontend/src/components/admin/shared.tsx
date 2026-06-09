import { Component } from 'react'

export class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: string }> {
  state = { hasError: false, error: '' }
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e.message } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: '#e53935' }}>
          <h3>页面加载异常</h3>
          <p style={{ fontSize: 13, color: '#999' }}>{this.state.error}</p>
          <button onClick={() => this.setState({ hasError: false })} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer' }}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}

export const Spinner = () => <div style={{ textAlign: 'center', color: '#999', padding: 40, fontSize: 13 }}>加载中...</div>

export const Empty = ({ msg = '暂无数据' }: { msg?: string }) => <div style={{ textAlign: 'center', color: '#bbb', padding: 40, fontSize: 13 }}>{msg}</div>

export const ErrorMsg = ({ msg, onRetry }: { msg: string; onRetry?: () => void }) => (
  <div style={{ color: '#e53935', fontSize: 13, padding: 12, background: '#fff0f0', borderRadius: 8, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
    <span style={{ flex: 1 }}>{msg}</span>
    {onRetry && <button onClick={onRetry} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#1976d2', fontSize: 12, whiteSpace: 'nowrap' }}>重试</button>}
  </div>
)

export const Card = ({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) => (
  <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #eee', overflow: 'hidden', ...style }}>{children}</div>
)

export const CardHeader = ({ title, action }: { title: string; action?: React.ReactNode }) => (
  <div style={{ padding: '14px 20px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14, color: '#333', background: '#fafafa', display: 'flex', alignItems: 'center' }}>
    {title}<div style={{ flex: 1 }} />{action}
  </div>
)

export const btnPrimary: React.CSSProperties = { background: '#1976d2', color: '#fff', border: 'none', borderRadius: 6, padding: '7px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
export const btnDangerSm: React.CSSProperties = { fontSize: 12, padding: '4px 10px', color: '#e53935', border: '1px solid #e53935', background: 'none', borderRadius: 4, cursor: 'pointer' }
export const inputStyle: React.CSSProperties = { padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', boxSizing: 'border-box' }
export const badge = (text: string, color: string) => <span style={{ fontSize: 11, color, background: `${color}15`, padding: '2px 6px', borderRadius: 4, marginLeft: 6 }}>{text}</span>

export function headers() {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const t = localStorage.getItem('token')
  if (t) h['Authorization'] = `Bearer ${t}`
  return h
}

export async function safeJson(res: Response): Promise<any> {
  const text = await res.text()
  try { return JSON.parse(text) }
  catch { return null }
}

export const API_BASE = '/api/v1'
