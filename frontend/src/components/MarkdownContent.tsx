import React, { useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getToken } from '../api'
import { CopyIcon, CheckIcon, DownloadIcon, ChevronDownIcon, ChevronUpIcon } from './icons'

/* 递归提取代码块文本（react-markdown 的 children 可能是 string/数组/元素） */
function codeText(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (Array.isArray(children)) return children.map(codeText).join('')
  if (children && typeof children === 'object' && 'props' in (children as any)) {
    return codeText((children as any).props.children)
  }
  return ''
}

/* 代码块：语言标签 + 一键复制 + 下载（通用 AI 对话方案，2026-10-25/26）——
   不再让用户整段手选复制；长代码默认折叠前 12 行 */
const LANG_EXT: Record<string, string> = {
  python: 'py', py: 'py', javascript: 'js', js: 'js', typescript: 'ts', ts: 'ts',
  bash: 'sh', sh: 'sh', shell: 'sh', json: 'json', html: 'html', css: 'css',
  sql: 'sql', java: 'java', go: 'go', rust: 'rs', c: 'c', cpp: 'cpp',
  yaml: 'yml', yml: 'yml', markdown: 'md', md: 'md', xml: 'xml', svg: 'svg',
  csv: 'csv', txt: 'txt', text: 'txt', ini: 'ini', toml: 'toml', dockerfile: 'Dockerfile',
}
const COLLAPSE_LINES = 15
const SHOW_LINES = 12

/* 任务清单项：可点击勾选（本地视觉态——不改写消息原文，刷新恢复） */
function TaskItem({ initial, children }: { initial: boolean; children: ReactNode }) {
  const [done, setDone] = useState(initial)
  return (
    <span style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <span onClick={() => setDone((d) => !d)}
        style={{
          width: 15, height: 15, borderRadius: 4, marginTop: 3, flexShrink: 0,
          border: `1.5px solid ${done ? 'var(--success)' : 'var(--text-muted)'}`,
          background: done ? 'var(--success)' : 'transparent',
          cursor: 'pointer', display: 'inline-flex', alignItems: 'center',
          justifyContent: 'center', transition: 'all 0.15s',
        }}>
        {done && (
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff"
            strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </span>
      <span style={{
        textDecoration: done ? 'line-through' : undefined,
        color: done ? 'var(--text-muted)' : undefined, flex: 1,
      }}>{children}</span>
    </span>
  )
}

function CodeBlock({ lang, text }: { lang: string; text: string }) {
  const [copied, setCopied] = useState(false)
  const [folded, setFolded] = useState(true)
  const lines = text.split('\n')
  const foldable = lines.length > COLLAPSE_LINES
  const shown = folded && foldable ? lines.slice(0, SHOW_LINES).join('\n') : text
  const copy = () => {
    navigator.clipboard?.writeText(text).catch(() => { /* 剪贴板不可用静默 */ })
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  const download = () => {
    const ext = LANG_EXT[lang.toLowerCase()] || 'txt'
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `snippet.${ext}`
    a.click()
    URL.revokeObjectURL(url)
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
        <span style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <button className="yuan-tip" data-tip="下载文件" aria-label="下载文件"
            onClick={download}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                     color: 'var(--text-muted)', display: 'flex', lineHeight: 1 }}>
            <DownloadIcon size={13} />
          </button>
          <button className="yuan-tip" data-tip={copied ? '已复制' : '复制代码'}
            aria-label="复制代码"
            onClick={copy}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                     color: copied ? 'var(--success)' : 'var(--text-muted)',
                     display: 'flex', lineHeight: 1, transition: 'color 0.15s' }}>
            {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
          </button>
        </span>
      </div>
      <pre style={{
        margin: 0, padding: 12, overflow: 'auto', fontSize: 13,
        fontFamily: 'monospace', lineHeight: 1.55,
      }}>
        <code>{shown}{folded && foldable ? `\n…（共 ${lines.length} 行）` : ''}</code>
      </pre>
      {foldable && (
        <button onClick={() => setFolded((f) => !f)}
          style={{
            width: '100%', padding: '4px 0', border: 'none', cursor: 'pointer',
            borderTop: '1px solid var(--border-light)', background: 'var(--bg-secondary)',
            fontSize: 11, color: 'var(--text-muted)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', gap: 4,
          }}>
          {folded ? <ChevronDownIcon size={12} /> : <ChevronUpIcon size={12} />}
          {folded ? '展开全部' : '收起'}
        </button>
      )}
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
        li: ({ children, className }) => {
          // 任务清单（- [ ]）：可点击勾选（2026-10-26；本地视觉态，不落库）
          const arr = Array.isArray(children) ? children : [children]
          const isTask = typeof className === 'string' && className.includes('task-list-item')
          if (isTask) {
            const inputChild = arr.find((c) => React.isValidElement(c) && (c as any).type === 'input')
            const initial = !!((inputChild as any)?.props?.checked)
            const rest = arr.filter((c) => !(React.isValidElement(c) && (c as any).type === 'input'))
            return (
              <li style={{ listStyle: 'none', marginBottom: 2 }}>
                <TaskItem initial={initial}>{rest}</TaskItem>
              </li>
            )
          }
          return <li style={{ marginBottom: 2 }}>{children}</li>
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default React.memo(MarkdownContentInner)
