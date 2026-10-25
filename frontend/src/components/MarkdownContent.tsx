import React, { useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getToken } from '../api'
import { CopyIcon, CheckIcon } from './icons'

/* 递归提取代码块文本（react-markdown 的 children 可能是 string/数组/元素） */
function codeText(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (Array.isArray(children)) return children.map(codeText).join('')
  if (children && typeof children === 'object' && 'props' in (children as any)) {
    return codeText((children as any).props.children)
  }
  return ''
}

/* 代码块：语言标签 + 一键复制（通用 AI 对话方案，2026-10-25）——
   不再让用户整段手选复制 */
function CodeBlock({ lang, text }: { lang: string; text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(text).catch(() => { /* 剪贴板不可用静默 */ })
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div style={{
      margin: '6px 0', borderRadius: 8, overflow: 'hidden',
      border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '4px 6px 4px 12px', background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border-light)',
      }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{lang}</span>
        <button
          className="yuan-tip" data-tip={copied ? '已复制' : '复制代码'}
          aria-label="复制代码"
          onClick={copy}
          style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 4,
            color: copied ? 'var(--success)' : 'var(--text-muted)',
            display: 'flex', lineHeight: 1, transition: 'color 0.15s',
          }}
        >
          {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
        </button>
      </div>
      <pre style={{
        margin: 0, padding: 12, overflow: 'auto', fontSize: 13,
        fontFamily: 'monospace', lineHeight: 1.55,
      }}>
        <code>{text}</code>
      </pre>
    </div>
  )
}

/* 知识星球资产图片无法带 Authorization 头 → 拼 ?token=（其它路径原样） */
function withAssetToken(src?: string): string | undefined {
  if (!src) return src
  if (src.startsWith('/api/v1/planet/asset/') && !src.includes('token=')) {
    return `${src}${src.includes('?') ? '&' : '?'}token=${getToken()}`
  }
  return src
}

function MarkdownContentInner({ content, indent, onImageExpand }: {
  content: string; indent?: boolean; onImageExpand?: (src: string) => void
}) {
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
            onClick={onImageExpand && src ? () => onImageExpand(withAssetToken(src) || '') : undefined}
            style={{
              maxWidth: '100%', borderRadius: 8, margin: '6px 0', border: '1px solid var(--border)',
              ...(onImageExpand ? { cursor: 'zoom-in' } : {}),
            }} />
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
          const lang = (className || '').replace('language-', '') || 'code'
          return <CodeBlock lang={lang} text={codeText(children)} />
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

export default React.memo(MarkdownContentInner)
