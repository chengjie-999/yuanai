import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function MarkdownContent({ content }: { content: string }) {
  if (!content) return null
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noreferrer" style={{ color: '#1976d2' }}>
            {children}
          </a>
        ),
        code: ({ className, children, ...props }) => {
          const isInline = !className
          if (isInline) {
            return <code style={{ background: '#f0f0f0', padding: '1px 4px', borderRadius: 3, fontSize: '0.9em' }} {...props}>{children}</code>
          }
          return (
            <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 8, overflow: 'auto', fontSize: 13 }}>
              <code className={className} {...props}>{children}</code>
            </pre>
          )
        },
        table: ({ children }) => (
          <div style={{ overflow: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13 }}>{children}</table>
          </div>
        ),
        th: ({ children }) => <th style={{ border: '1px solid #ddd', padding: '6px 10px', background: '#f5f5f5' }}>{children}</th>,
        td: ({ children }) => <td style={{ border: '1px solid #ddd', padding: '6px 10px' }}>{children}</td>,
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
