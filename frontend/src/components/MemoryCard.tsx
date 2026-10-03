import { useState, useEffect } from 'react'
import { fetchMemory, saveMemory } from '../api'
import { XIcon, EditIcon, TrashIcon } from './icons'

/* 设置页「我的记忆」卡 — 透明可编辑的长期记忆（每行一条事实，随时可改可删） */

const C = {
  card: { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' } as const,
  title: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' } as const,
  sub: { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 } as const,
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid var(--border-light)', gap: 16 } as const,
  hint: { fontSize: 11, color: 'var(--text-muted)', marginTop: 2 } as const,
  btn: { padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', fontSize: 12.5, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 } as const,
  btnPrimary: { padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' } as const,
}

export default function MemoryCard() {
  const [memory, setMemory] = useState('')
  const [count, setCount] = useState(0)
  const [maxItems, setMaxItems] = useState(100)
  const [maxChars, setMaxChars] = useState(2000)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [msg, setMsg] = useState('')
  const [msgErr, setMsgErr] = useState(false)
  const [saving, setSaving] = useState(false)

  const refresh = () => {
    fetchMemory().then(d => {
      setMemory(d.memory)
      setCount(d.count)
      setMaxItems(d.max_items)
      setMaxChars(d.max_chars)
    })
  }

  useEffect(() => { refresh() }, [])

  const openEdit = () => {
    setDraft(memory)
    setMsg('')
    setMsgErr(false)
    setEditing(true)
  }

  const doSave = async (text: string) => {
    setSaving(true)
    setMsgErr(false)
    setMsg('')
    const r = await saveMemory(text)
    setSaving(false)
    if (!r.ok) {
      setMsgErr(true)
      setMsg(r.detail || '保存失败')
      return false
    }
    // 以服务端归一化后的文本刷新（透明：所见即所存）
    setMemory(r.memory ?? text)
    setCount(r.count ?? 0)
    setEditing(false)
    return true
  }

  const doClear = () => {
    if (window.confirm('确定清空全部记忆吗？小元将忘记所有关于你的信息。')) {
      doSave('')
    }
  }

  const lines = memory ? memory.split('\n').filter(l => l.trim()) : []

  const editPanel = editing && (
    <>
      <div onClick={() => !saving && setEditing(false)}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 200 }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 420, maxWidth: '90vw', background: 'var(--bg-primary)', zIndex: 201, boxShadow: '-4px 0 24px rgba(0,0,0,0.12)', display: 'flex', flexDirection: 'column', animation: 'slide-in-right 0.25s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 24px', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>编辑我的记忆</h2>
          <button onClick={() => !saving && setEditing(false)} title="关闭" aria-label="关闭"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px', lineHeight: 1, display: 'flex' }}><XIcon size={16} /></button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          <textarea value={draft} onChange={e => setDraft(e.target.value)}
            style={{ width: '100%', minHeight: 320, boxSizing: 'border-box', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13.5, lineHeight: 1.7, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)', resize: 'vertical', fontFamily: 'inherit' }}
            placeholder={'每行一条事实，例如：\n用户是数据分析师，常用 pandas\n用户怕辣，不吃香菜\n在做一个关于跨境电商的项目'} />
          <div style={C.hint}>
            删除某一行 = 让小元忘记这条；共 {draft ? draft.split('\n').filter(l => l.trim()).length : 0} 条 · {draft.length}/{maxChars} 字（上限 {maxItems} 条 / {maxChars} 字）
          </div>
          {msg && (
            <div style={{ fontSize: 13, color: msgErr ? 'var(--danger)' : 'var(--success)', marginTop: 12, padding: '8px 12px', borderRadius: 6, background: msgErr ? 'rgba(244,71,71,0.08)' : 'rgba(106,153,85,0.08)' }}>{msg}</div>
          )}
        </div>
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={() => !saving && setEditing(false)}
            style={{ padding: '10px 24px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', fontSize: 14, cursor: 'pointer' }}>取消</button>
          <button onClick={() => doSave(draft)} disabled={saving}
            style={{ ...C.btnPrimary, fontSize: 14, padding: '10px 24px', opacity: saving ? 0.6 : 1 }}>保存</button>
        </div>
      </div>
      <style>{`@keyframes slide-in-right { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>
    </>
  )

  return (
    <div style={C.card}>
      <div style={C.title}>
        我的记忆
        <span style={C.sub}>　小元在对话中记住的关于你的信息（每行一条，随时可改可删）</span>
      </div>
      {lines.length === 0 ? (
        <div style={{ padding: '28px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
          还没有记忆。在对话里说「记住……」，小元就会记在这里
        </div>
      ) : (
        <div style={{ padding: '12px 20px 4px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            共 {count} 条 · {memory.length}/{maxChars} 字
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.9 }}>
            {lines.map((l, i) => (
              <li key={i} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={l}>{l}</li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ ...C.row, borderBottom: 'none', paddingTop: lines.length === 0 ? 12 : 10 }}>
        <div style={C.hint}>AI 自动整理的事实也会写到这里</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={openEdit} style={C.btn} className="yuan-tip" data-tip="修改或删除记忆" aria-label="编辑记忆">
            <EditIcon size={13} /> 编辑
          </button>
          {lines.length > 0 && (
            <button onClick={doClear} style={{ ...C.btn, color: 'var(--danger)', borderColor: 'transparent' }} className="yuan-tip" data-tip="清空全部记忆" aria-label="清空记忆">
              <TrashIcon size={13} /> 清空
            </button>
          )}
        </div>
      </div>
      {editPanel}
    </div>
  )
}
