import { useState } from 'react'
import type { OutlineNode } from './PlanetOutline'

/* SVG 图形化导图视图：向右树形布局，节点可折叠。
   零依赖手写布局：x = 深度 × 间距，y 按子树行数居中。 */
const DX = 170
const ROW_H = 36
const NODE_H = 26
const NODE_R = 8

function measure(n: OutlineNode): number {
  if (!n.children.length) return 1
  return Math.max(1, n.children.reduce((s, c) => s + measure(c), 0))
}

interface Placed { node: OutlineNode; depth: number; y: number; children: Placed[]; key: string }

function place(node: OutlineNode, depth: number, y0: number, key: string): Placed {
  const h = measure(node)
  const y = y0 + h / 2
  let cy = y0
  const children = node.children.map((c, i) => {
    const p = place(c, depth + 1, cy, `${key}/${i}`)
    cy += measure(c)
    return p
  })
  return { node, depth, y, children, key }
}

function collectVisible(p: Placed, collapsed: Set<string>, out: Placed[]) {
  out.push(p)
  if (!collapsed.has(p.key)) p.children.forEach((c) => collectVisible(c, collapsed, out))
}

export default function PlanetMapView({ tree }: { tree: any }) {
  const roots: OutlineNode[] = tree?.children || []
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  if (!roots.length) return <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 20, textAlign: 'center' }}>空导图</div>

  const placedRoots = roots.map((n, i) => place(n, 0, 0, String(i)))
  const totalRows = placedRoots.reduce((s, r) => s + measure(r.node), 0)
  const height = Math.max(totalRows * ROW_H, 120)
  const width = 1400

  const visible: Placed[] = []
  placedRoots.forEach((r) => collectVisible(r, collapsed, visible))
  const maxDepth = Math.max(...visible.map((v) => v.depth), 1)

  const toggle = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div style={{ overflow: 'auto', maxHeight: '100%' }}>
      <svg width={Math.max(width, maxDepth * DX + 220)} height={height} style={{ display: 'block' }}>
        {visible.map((p) => (
          <g key={p.key}>
            {!collapsed.has(p.key) && p.children.map((c, i) => {
              const x1 = p.depth * DX + 150
              const x2 = c.depth * DX + 150
              return (
                <path key={i}
                  d={`M ${x1} ${p.y * ROW_H + NODE_H / 2} C ${(x1 + x2) / 2} ${p.y * ROW_H + NODE_H / 2}, ${(x1 + x2) / 2} ${c.y * ROW_H + NODE_H / 2}, ${x2 - 6} ${c.y * ROW_H + NODE_H / 2}`}
                  fill="none" stroke="var(--border)" strokeWidth={1.5} />
              )
            })}
            {p.depth > 0 && (
              <circle cx={p.depth * DX + 150 - 8} cy={p.y * ROW_H + NODE_H / 2} r={2.5} fill="var(--text-muted)" />
            )}
          </g>
        ))}
        {visible.map((p) => {
          const hasKids = p.node.children.length > 0
          const label = p.node.title.length > 18 ? p.node.title.slice(0, 18) + '…' : p.node.title
          const w = Math.max(40, label.length * 13 + 24)
          const x = p.depth * DX + 150
          const y = p.y * ROW_H
          return (
            <g key={`n-${p.key}`} onClick={() => hasKids && toggle(p.key)}
              style={{ cursor: hasKids ? 'pointer' : 'default' }}>
              <rect x={x} y={y} width={w} height={NODE_H} rx={NODE_R}
                fill={p.depth === 0 ? 'var(--accent)' : 'var(--bg-input)'}
                stroke={p.depth === 0 ? 'var(--accent)' : 'var(--border)'} strokeWidth={1.2} />
              <text x={x + w / 2} y={y + NODE_H / 2 + 4.5} textAnchor="middle" fontSize={12.5}
                fill={p.depth === 0 ? '#fff' : 'var(--text-primary)'}>{label}</text>
              {hasKids && (
                <text x={x + w + 6} y={y + NODE_H / 2 + 4}
                  fontSize={11} fill="var(--text-muted)" pointerEvents="none">
                  {collapsed.has(p.key) ? '+' : '−'}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
