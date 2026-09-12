import { useState } from 'react'
import { ChevronDownIcon, ChevronRightIcon } from '../icons'

export interface OutlineNode {
  title: string
  content?: string
  images?: { alt: string; src: string }[]
  children: OutlineNode[]
}

/* 导图大纲视图：可折叠的缩进树（tree.json 渲染） */
export default function PlanetOutline({ tree }: { tree: any }) {
  const roots: OutlineNode[] = tree?.children || []
  if (!roots.length) return <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>空导图</div>
  return (
    <div style={{ padding: '4px 0' }}>
      {roots.map((n, i) => <OutlineRow key={i} node={n} depth={0} />)}
    </div>
  )
}

function OutlineRow({ node, depth }: { node: OutlineNode; depth: number }) {
  const [open, setOpen] = useState(true)
  const hasKids = node.children.length > 0
  const dotOpacity = Math.max(0.35, 0.85 - depth * 0.08)
  return (
    <div style={{ paddingLeft: depth > 0 ? 14 : 0 }}>
      <div onClick={() => hasKids && setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 4px', borderRadius: 6, cursor: hasKids ? 'pointer' : 'default', userSelect: 'none' }}
        onMouseEnter={(e) => { if (hasKids) (e.currentTarget as HTMLElement).style.background = 'var(--hover-bg)' }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
      >
        {hasKids
          ? (open ? <ChevronDownIcon size={12} /> : <ChevronRightIcon size={12} />)
          : <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', opacity: dotOpacity, flexShrink: 0 }} />}
        <span style={{
          fontSize: 13, lineHeight: 1.5,
          color: depth === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
          fontWeight: depth === 0 ? 600 : 400,
        }}>{node.title}</span>
      </div>
      {node.content && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 18, whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
          {node.content.slice(0, 200)}
        </div>
      )}
      {open && hasKids && node.children.map((c, i) => <OutlineRow key={i} node={c} depth={depth + 1} />)}
    </div>
  )
}
