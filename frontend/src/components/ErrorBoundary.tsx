import { Component } from 'react'

export class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean; error: string }> {
  state = { hasError: false, error: '' }
  static getDerivedStateFromError(e: Error) { return { hasError: true, error: e.message } }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--danger)' }}>
          <h3>页面加载异常</h3>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{this.state.error}</p>
          <button onClick={() => this.setState({ hasError: false })} style={{ marginTop: 12, padding: '6px 16px', cursor: 'pointer' }}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}
