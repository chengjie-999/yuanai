import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getToken } from '../api'

/* 知识星球资产图片无法带 Authorization 头 → 拼 ?token=（其它路径原样） */
function withAssetToken(src?: string): string | undefined {
  if (!src) return src
  if (src.startsWith('/api/v1/planet/asset/') && !src.includes('token=')) {
    return `${src}${src.includes('?') ? '&' : '?'}token=${getToken()}`
  }
  return src
}

function MarkdownContent({ content, indent }: { content: string; indent?: boolean }) {
  if (!content) return null
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>
            {children}
          </a>
        ),
        img: ({ src, alt }) => (
          <img src={withAssetToken(src)} alt={alt || ''} loading="lazy"
            style={{ maxWidth: '100%', borderRadius: 8, margin: '6px 0', border: '1px solid var(--border)' }} />
        ),
        h1: ({ children }) => <h1 style={{ fontSize: 22, fontWeight: 700, margin: '18px 0 8px', color: 'var(--text-primary)' }}>{children}</h1>,
        h2: ({ children }) => <h2 style={{ fontSize: 18, fontWeight: 700, margin: '16px 0 6px', color: 'var(--text-primary)' }}>{children}</h2>,
        h3: ({ children }) => <h3 style={{ fontSize: 15, fontWeight: 600, margin: '12px 0 4px', color: 'var(--text-primary)' }}>{children}</h3>,
        p: ({ children }) => <p style={{ margin: '4px 0', lineHeight: 1.7, textIndent: indent ? '2em' : undefined }}>{children}</p>,
        code: ({ className, children, ...props }) => {
          const isInline = !className
          if (isInline) {
            return <code style={{ background: 'var(--bg-tertiary)', padding: '1px 4px', borderRadius: 3, fontSize: '0.9em', color: 'var(--text-primary)' }} {...props}>{children}</code>
          }
          return (
            <pre style={{ background: 'var(--bg-tertiary)', padding: 12, borderRadius: 8, overflow: 'auto', fontSize: 13, border: '1px solid var(--border-light)' }}>
              <code className={className} {...props}>{children}</code>
            </pre>
          )
        },
        table: ({ children }) => (
          <div style={{ overflow: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>{children}</table>
          </div>
        ),
        th: ({ children }) => <th style={{ border: '1px solid var(--border)', padding: '6px 10px', background: 'var(--bg-secondary)' }}>{children}</th>,
        td: ({ children }) => <td style={{ border: '1px solid var(--border)', padding: '6px 10px' }}>{children}</td>,
        ul: ({ children }) => <ul style={{ paddingLeft: 24, margin: '4px 0' }}>{children}</ul>,
        ol: ({ children }) => <ol style={{ paddingLeft: 24, margin: '4px 0' }}>{children}</ol>,
        li: ({ children }) => <li style={{ marginBottom: 2 }}>{children}</li>,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default MarkdownContent
