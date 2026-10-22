import Mascot from './Mascot'

/** 404 页 — 公开侧与应用内共用：吉祥物 + 返回按钮（2026-10-22 新增） */
export default function NotFoundPage({ backTo = '/', backText = '返回首页' }: { backTo?: string; backText?: string }) {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 20,
      padding: 24, textAlign: 'center',
    }}>
      <Mascot size={96} />
      <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)' }}>404</div>
      <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>页面不存在或已被移动</div>
      <a href={backTo} style={{
        padding: '8px 24px', borderRadius: 6, background: 'var(--accent)', color: '#fff',
        fontSize: 14, fontWeight: 500, textDecoration: 'none',
      }}>
        {backText}
      </a>
    </div>
  )
}
