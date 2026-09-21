import { useState } from 'react'
import MarkdownContent from '../MarkdownContent'

/* 笔记编辑器：textarea 直接编辑 + 预览切换（项目无 markdown 编辑器，textarea 足够） */
export default function NoteEditor({ initial, onSave, onCancel }: {
  initial: string
  onSave: (content: string) => Promise<void>
  onCancel: () => void
}) {
  const [content, setContent] = useState(initial)
  const [preview, setPreview] = useState(false)
  const [saving, setSaving] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={() => setPreview(!preview)} className="btn btn-outline btn-sm">{preview ? '编辑' : '预览'}</button>
        <div style={{ flex: 1 }} />
        <button onClick={onCancel} className="btn btn-outline btn-sm">取消</button>
        <button disabled={saving} className="btn btn-primary btn-sm"
          onClick={async () => { setSaving(true); try { await onSave(content) } finally { setSaving(false) } }}>
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
      {preview ? (
        <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', background: 'var(--bg-primary)' }}>
          <MarkdownContent content={content} indent />
        </div>
      ) : (
        <textarea value={content} onChange={(e) => setContent(e.target.value)} autoFocus
          style={{
            width: '100%', minHeight: 420, padding: 12, borderRadius: 8,
            border: '1px solid var(--border)', background: 'var(--bg-input)',
            color: 'var(--text-primary)', fontSize: 14, fontFamily: 'inherit',
            lineHeight: 1.7, resize: 'vertical', outline: 'none',
          }} />
      )}
    </div>
  )
}
