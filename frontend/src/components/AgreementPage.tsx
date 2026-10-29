import { useState, useEffect } from 'react'
import LandingHeader from './LandingHeader'
import MarkdownContent from './MarkdownContent'
import { API_BASE } from '../api'
import { trackVisit } from '../api'
import { usePageMeta } from '../hooks/usePageMeta'
import { ICP_BEIAN_NUMBER, ICP_BEIAN_URL, POLICE_BEIAN_NUMBER, POLICE_BEIAN_URL } from '../config/site'

/* ============================================================
   协议公开页（免登录，/terms /privacy /rules）——C11 合规（2026-10-29）
   文本单一事实源 = docs/agreements/*.md（后端实时读取，改文档即改页面）
   ============================================================ */

const DOCS: Record<string, { title: string; desc: string }> = {
  terms: { title: '用户协议', desc: '小元AI 平台服务协议' },
  privacy: { title: '隐私政策', desc: '我们如何收集、使用与保护您的个人信息' },
  rules: { title: '服务规则', desc: '内容安全、投诉举报与使用规则' },
}

export default function AgreementPage({ name }: { name: string }) {
  const doc = DOCS[name] || DOCS.terms
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  usePageMeta({ title: `${doc.title} - 小元AI`, description: doc.desc })

  // 加载 + 重试（2026-10-30 修复「空壳」：此前 fetch 完成前页面无任何状态提示）
  const load = () => {
    setLoading(true)
    setError('')
    fetch(`${API_BASE}/docs/agreement/${name}`, { headers: { Accept: 'text/markdown' } })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text() })
      .then((t) => { setContent(t); setLoading(false) })
      .catch(() => { setError('协议文档加载失败，请检查网络后重试'); setLoading(false) })
  }

  useEffect(() => {
    trackVisit(`/agreement/${name}`)
    setContent('')
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column' }}>
      <LandingHeader />
      <div style={{
        maxWidth: 820, width: '100%', margin: '24px auto 60px', padding: '0 20px',
        boxSizing: 'border-box',
      }}>
        <div style={{
          background: 'var(--bg-primary)', border: '1px solid var(--border-light)',
          borderRadius: 14, padding: '28px 32px',
        }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px' }}>{doc.title}</h1>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>{doc.desc}</div>
          {loading && <div style={{ textAlign: 'center', padding: '40px 0', fontSize: 13, color: 'var(--text-muted)' }}>文档加载中...</div>}
          {error && (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: 13, color: 'var(--danger)', marginBottom: 12 }}>{error}</div>
              <button onClick={load}
                style={{ padding: '6px 20px', borderRadius: 6, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', cursor: 'pointer', fontSize: 13 }}>
                重试
              </button>
            </div>
          )}
          {!loading && !error && content && <MarkdownContent content={content} />}
        </div>
      </div>
      <div style={{ marginTop: 'auto', textAlign: 'center', padding: '20px 16px 28px', fontSize: 12, color: 'var(--text-muted)' }}>
        <span>小元AI · 云边协同多智能体平台</span>
        {ICP_BEIAN_NUMBER && (
          <a href={ICP_BEIAN_URL} target="_blank" rel="noreferrer"
            style={{ color: 'var(--text-muted)', textDecoration: 'none', marginLeft: 8 }}>
            {ICP_BEIAN_NUMBER}
          </a>
        )}
        {POLICE_BEIAN_NUMBER && (
          <a href={POLICE_BEIAN_URL} target="_blank" rel="noreferrer"
            style={{ color: 'var(--text-muted)', textDecoration: 'none', marginLeft: 8 }}>
            {POLICE_BEIAN_NUMBER}
          </a>
        )}
      </div>
    </div>
  )
}
