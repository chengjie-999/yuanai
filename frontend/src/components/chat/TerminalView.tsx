import { useState } from 'react'
import type { ToolCall } from '../../types'
import { TerminalIcon, CopyIcon, CheckIcon, ChevronDownIcon, ChevronUpIcon } from '../icons'

/* ============================================================
   P2 对话内嵌终端面板（2026-10-23）
   把 Claude Code 桥接的命令类工具调用（Bash/Read/Write/Edit/Glob/Grep）
   渲染为「$ 命令 → 输出」终端序列：黑底等宽、折叠/展开、逐命令复制。
   普通工具（搜索/脚本/计划等）仍走 ToolCallCard，不进终端视图。
   ============================================================ */

const FILE_TOOL_VERBS: Record<string, string> = {
  Read: 'read', Write: 'write', Edit: 'edit', Glob: 'glob', Grep: 'grep',
}

/* args 可能是字符串 JSON 或对象（后端 tool_start 直发 dict，2026-10-21 修复） */
function parseArgs(args: unknown): Record<string, unknown> | null {
  try {
    const o = typeof args === 'string' ? JSON.parse(args) : args
    if (o && typeof o === 'object' && !Array.isArray(o)) return o as Record<string, unknown>
  } catch { /* 忽略 */ }
  return null
}

export function isTerminalCall(tc: ToolCall): boolean {
  const o = parseArgs(tc.args)
  if (!o) return false
  if (typeof o.command === 'string') return true
  if (tc.name in FILE_TOOL_VERBS) return true
  return false
}

/* 终端行命令文本：bash 显示原命令；文件类工具显示 read/write <路径> 形态 */
function commandText(tc: ToolCall): string {
  const o = parseArgs(tc.args)
  if (o && typeof o.command === 'string') return o.command
  const verb = FILE_TOOL_VERBS[tc.name]
  const arg = (o && (o.file_path || o.pattern || o.path)) || ''
  return [verb, String(arg)].filter(Boolean).join(' ')
}

const MAX_OUTPUT = 2000  // 显示截断（对齐工具输出回传上限）

/* A1 精简（2026-11-03 用户拍板）：终端面板默认折叠（命令/输出属专业细节）；
   流式期间（当前正在执行的命令）由父层传 defaultOpen 展开显示当前活动 */
export default function TerminalView({ calls, defaultOpen = false }: { calls: ToolCall[]; defaultOpen?: boolean }) {
  const [collapsed, setCollapsed] = useState(!defaultOpen)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const anyRunning = calls.some((tc) => tc.status === 'running')

  const copy = (idx: number, text: string) => {
    navigator.clipboard?.writeText(text).catch(() => { /* 剪贴板不可用时静默 */ })
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx((c) => (c === idx ? null : c)), 1500)
  }

  return (
    <div style={{
      marginTop: 8, marginBottom: 4, borderRadius: 8, overflow: 'hidden',
      background: 'var(--terminal-bg)', border: '1px solid var(--terminal-border)',
      fontSize: 12.5, color: 'var(--terminal-text)',
    }}>
      {/* 头部：终端图标 + 命令数 + 执行中指示 + 折叠开关 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
        cursor: 'pointer', userSelect: 'none',
        background: 'rgba(255,255,255,0.03)',
      }} onClick={() => setCollapsed((c) => !c)}>
        <TerminalIcon size={14} style={{ color: 'var(--terminal-prompt)' }} />
        <span style={{ fontWeight: 600, fontSize: 12.5, flex: 1 }}>终端 · {calls.length} 条命令</span>
        {anyRunning && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0,
            fontSize: 11.5, color: 'var(--warning)',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: 'var(--warning)',
              animation: 'pulse 1s ease-in-out infinite',
            }} />
            执行中
          </span>
        )}
        <span style={{ display: 'flex', color: 'var(--text-muted)' }}>
          {collapsed ? <ChevronDownIcon size={13} /> : <ChevronUpIcon size={13} />}
        </span>
      </div>
      {!collapsed && calls.map((tc, idx) => {
        const output = tc.result || ''
        return (
          <div key={idx} style={{ padding: '6px 12px 8px', borderTop: '1px solid var(--terminal-border)' }}>
            {/* 命令行：$ 提示符 + 命令 + 状态/复制 */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <span style={{ color: 'var(--terminal-prompt)', fontFamily: 'monospace', flexShrink: 0 }}>$</span>
              <span style={{
                fontFamily: 'monospace', fontSize: 12, flex: 1, lineHeight: 1.5,
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>{commandText(tc)}</span>
              {tc.status === 'running' && (
                <span style={{ color: 'var(--warning)', fontSize: 11.5, flexShrink: 0, paddingTop: 1 }}>执行中…</span>
              )}
              {tc.status !== 'running' && (
                <button
                  className="yuan-tip" data-tip="复制命令"
                  aria-label="复制命令"
                  onClick={(e) => { e.stopPropagation(); copy(idx, commandText(tc)) }}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                    color: copiedIdx === idx ? 'var(--success)' : 'var(--text-muted)',
                    display: 'flex', flexShrink: 0, transition: 'color 0.15s',
                  }}>
                  {copiedIdx === idx ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
                </button>
              )}
            </div>
            {/* 输出区：等宽原文（长输出内部滚动） */}
            {tc.status === 'done' && output && (
              <pre style={{
                margin: '4px 0 0 0', fontFamily: 'monospace', fontSize: 11.5,
                lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                color: 'var(--terminal-text)', opacity: 0.85,
                maxHeight: 180, overflowY: 'auto', paddingLeft: 16,
              }}>
                {output.length > MAX_OUTPUT ? output.slice(0, MAX_OUTPUT) + '\n...(输出过长已截断)' : output}
              </pre>
            )}
            {tc.status === 'error' && (
              <pre style={{
                margin: '4px 0 0 0', fontFamily: 'monospace', fontSize: 11.5,
                lineHeight: 1.55, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                color: 'var(--danger)', maxHeight: 180, overflowY: 'auto', paddingLeft: 16,
              }}>
                {output}
              </pre>
            )}
          </div>
        )
      })}
    </div>
  )
}
