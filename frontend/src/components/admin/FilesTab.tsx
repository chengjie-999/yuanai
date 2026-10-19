import { useState, useEffect, useMemo, useRef } from 'react'
import { Spinner, Empty, ErrorMsg, Card, safeJson, headers, API_BASE } from './shared'
import { FolderIcon, FileIcon, XIcon } from '../icons'
import { useSecuredUrl, fetchSseToken } from '../chat/helpers'
import MarkdownContent from '../MarkdownContent'

/* HTML 渲染预览：沙箱 iframe（sse token）+ 源码切换 */
function HtmlPreview({ path, content, name }: { path: string; content: string; name: string }) {
  const [showSource, setShowSource] = useState(false)
  const src = useSecuredUrl(`${API_BASE}/admin/file-html?path=${encodeURIComponent(path)}`)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <button onClick={() => setShowSource(v => !v)}
          style={{ fontSize: 12, padding: '4px 10px', border: '1px solid var(--border)', background: 'var(--bg-secondary)', borderRadius: 4, cursor: 'pointer', color: 'var(--text-secondary)' }}>
          {showSource ? '渲染' : '源码'}
        </button>
      </div>
      {showSource ? (
        <pre style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)' }}>{content}</pre>
      ) : (
        <iframe src={src} sandbox="allow-scripts" title={name}
          style={{ width: '100%', height: '70vh', border: '1px solid var(--border)', borderRadius: 8, background: '#fff' }} />
      )}
    </div>
  )
}

/* Markdown 渲染预览：复用聊天页渲染器（表格/代码/图片）+ 源码切换 */
function MarkdownPreview({ content }: { content: string }) {
  const [showSource, setShowSource] = useState(false)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <button onClick={() => setShowSource(v => !v)}
          style={{ fontSize: 12, padding: '4px 10px', border: '1px solid var(--border)', background: 'var(--bg-secondary)', borderRadius: 4, cursor: 'pointer', color: 'var(--text-secondary)' }}>
          {showSource ? '渲染' : '源码'}
        </button>
      </div>
      {showSource ? (
        <pre style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)' }}>{content}</pre>
      ) : (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '14px 20px', maxHeight: '70vh', overflow: 'auto' }}>
          <MarkdownContent content={content} />
        </div>
      )}
    </div>
  )
}

/* CSV 表格预览（前 100 行；引号感知的简单解析） */
function CsvPreview({ content }: { content: string }) {
  const parsed = useMemo(() => {
    try {
      const rows: string[][] = []
      let row: string[] = [], cell = '', inQ = false
      for (let i = 0; i < content.length; i++) {
        const ch = content[i]
        if (inQ) {
          if (ch === '"') { if (content[i + 1] === '"') { cell += '"'; i++ } else inQ = false }
          else cell += ch
        } else if (ch === '"') inQ = true
        else if (ch === ',') { row.push(cell); cell = '' }
        else if (ch === '\n' || ch === '\r') {
          if (ch === '\r' && content[i + 1] === '\n') i++
          row.push(cell); cell = ''; rows.push(row); row = []
        } else cell += ch
      }
      if (cell !== '' || row.length) { row.push(cell); rows.push(row) }
      return rows.filter(r => r.some(c => c.trim() !== '')).slice(0, 101)
    } catch { return [] }
  }, [content])
  if (!parsed.length) return <pre style={{ fontSize: 13, color: 'var(--text-muted)' }}>无法解析 CSV</pre>
  const head = parsed[0], body = parsed.slice(1, 100)
  return (
    <div style={{ overflow: 'auto', maxHeight: '65vh', border: '1px solid var(--border)', borderRadius: 8 }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 12, minWidth: '100%' }}>
        <thead><tr>{head.map((h, i) => (
          <th key={i} style={{ padding: '7px 10px', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', whiteSpace: 'nowrap', textAlign: 'left', position: 'sticky', top: 0 }}>{h}</th>))}</tr></thead>
        <tbody>{body.map((r, i) => (
          <tr key={i} style={{ borderTop: '1px solid var(--border-light)' }}>{r.map((c, j) => (
            <td key={j} style={{ padding: '6px 10px', whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>{c}</td>))}</tr>))}</tbody>
      </table>
      {parsed.length > 100 && <div style={{ padding: 8, fontSize: 11, color: 'var(--text-muted)' }}>仅展示前 100 行（共 {parsed.length - 1} 行数据）</div>}
    </div>
  )
}

/* JSON 美化预览 */
function JsonPreview({ content }: { content: string }) {
  const pretty = useMemo(() => {
    try { return JSON.stringify(JSON.parse(content), null, 2) }
    catch { return null }
  }, [content])
  if (pretty === null) return <pre style={{ fontSize: 13, color: 'var(--danger)' }}>JSON 解析失败</pre>
  return <pre style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 16, fontSize: 12.5, lineHeight: 1.5, overflow: 'auto', maxHeight: '65vh', color: 'var(--text-primary)' }}>{pretty}</pre>
}

/* 音视频原生播放器（sse token URL） */
function MediaPreview({ path, ext }: { path: string; ext: string }) {
  const src = useSecuredUrl(`${API_BASE}/admin/file-media?path=${encodeURIComponent(path)}`)
  const isAudio = ['.mp3', '.wav', '.m4a', '.ogg'].includes(ext)
  return isAudio
    ? <audio src={src} controls style={{ width: '100%' }} />
    : <video src={src} controls style={{ width: '100%', maxHeight: '65vh', borderRadius: 8 }} />
}

/* PDF：新标签页打开（浏览器原生查看器；沙箱 iframe 会禁插件） */
function PdfPreview({ path }: { path: string }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    fetchSseToken().then(tok => {
      setUrl(`${API_BASE}/admin/file-media?path=${encodeURIComponent(path)}${tok ? `&token=${tok}` : ''}`)
    }).catch(() => {})
  }, [path])
  return (
    <div style={{ textAlign: 'center', padding: 30 }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 14 }}>PDF 文件用浏览器原生查看器打开</div>
      <button onClick={() => { if (url) window.open(url, '_blank') }}
        style={{ padding: '10px 24px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>
        在新标签页打开
      </button>
    </div>
  )
}

export default function FilesTab() {
  const [dirs, setDirs] = useState<{ name: string; path: string; is_dir: boolean; size_kb: number }[]>([])
  const [currentPath, setCurrentPath] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const [busy, setBusy] = useState('')  // 进行中的操作提示
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [renameTarget, setRenameTarget] = useState<{ path: string; name: string } | null>(null)
  const [renameDraft, setRenameDraft] = useState('')
  const [mkdirDraft, setMkdirDraft] = useState('')

  const load = async (p: string) => {
    setLoading(true); setError(''); setCurrentPath(p)
    try {
      const res = await fetch(`${API_BASE}/admin/files?path=` + encodeURIComponent(p), { headers: headers() })
      const d = await safeJson(res)
      if (d && d.items) setDirs(d.items); else if (d && d.error) setError(d.error)
    } catch { setError('加载文件列表失败') }
    setLoading(false)
  }
  useEffect(() => { load('') }, [])

  const goUp = () => { const parts = currentPath.split(/[/\\]/).filter(Boolean); parts.pop(); load(parts.join('/')) }

  const api = async (url: string, init?: RequestInit) => {
    const res = await fetch(url, { ...init, headers: headers() })
    const d = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error((d as any).detail || `HTTP ${res.status}`)
    return d
  }

  const handleUpload = async (f: File) => {
    setBusy('上传中...')
    try {
      const form = new FormData()
      form.append('file', f)
      const token = localStorage.getItem('token') || sessionStorage.getItem('token')
      const res = await fetch(`${API_BASE}/admin/file/upload?path=${encodeURIComponent(currentPath)}`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      })
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error((d as any).detail || '上传失败') }
      await load(currentPath)
    } catch (e: any) { setError(e.message) }
    setBusy('')
  }

  const handleMkdir = async () => {
    if (!mkdirDraft.trim()) return
    setBusy('创建中...')
    try {
      await api(`${API_BASE}/admin/file/mkdir`, { method: 'POST', body: JSON.stringify({ path: currentPath, name: mkdirDraft.trim() }) })
      setMkdirDraft('')
      await load(currentPath)
    } catch (e: any) { setError(e.message) }
    setBusy('')
  }

  const handleRename = async () => {
    if (!renameTarget || !renameDraft.trim()) return
    setBusy('重命名中...')
    try {
      await api(`${API_BASE}/admin/file/rename`, { method: 'POST', body: JSON.stringify({ path: renameTarget.path, name: renameDraft.trim() }) })
      setRenameTarget(null)
      await load(currentPath)
    } catch (e: any) { setError(e.message) }
    setBusy('')
  }

  const handleDelete = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (!window.confirm(`确定删除 ${d.name} 吗？${d.is_dir ? '（目录必须为空）' : '（不可恢复）'}`)) return
    setBusy('删除中...')
    try {
      await api(`${API_BASE}/admin/file/delete?path=${encodeURIComponent(d.path)}`, { method: 'DELETE' })
      await load(currentPath)
    } catch (e: any) { setError(e.message) }
    setBusy('')
  }

  const handlePreview = async (d: { name: string; path: string; is_dir: boolean }) => {
    if (d.is_dir) { load(d.path); return }
    setError('')
    try {
      const res = await fetch(`${API_BASE}/admin/file/read?path=` + encodeURIComponent(d.path), { headers: headers() })
      const r = await safeJson(res)
      if (r && r.error) { setError(r.error); return }
      setPreview({ ...r, name: d.name })
    } catch { setError('读取文件失败') }
  }

  return (
    <div>
      {error && <ErrorMsg msg={error} />}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
        {currentPath && <button onClick={goUp} title="上级目录" aria-label="上级目录" style={{ fontSize: 12, padding: '4px 10px', border: '1px solid var(--border)', background: 'var(--bg-primary)', borderRadius: 4, cursor: 'pointer', color: 'var(--text-primary)' }}>上级目录</button>}
        <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-primary)' }}>data/{currentPath || '.'}</span>
        <button onClick={() => load(currentPath)} title="刷新" aria-label="刷新" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, color: 'var(--accent)' }}>刷新</button>
        <div style={{ flex: 1 }} />
        <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }}
          onChange={(e) => { const fs = Array.from(e.target.files || []); fs.forEach(handleUpload); e.target.value = '' }} />
        <button onClick={() => fileInputRef.current?.click()} disabled={!!busy}
          style={{ fontSize: 12, padding: '5px 14px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', cursor: 'pointer', color: 'var(--text-primary)' }}>上传文件</button>
        <input value={mkdirDraft} onChange={(e) => setMkdirDraft(e.target.value)} placeholder="新文件夹名"
          style={{ fontSize: 12, padding: '5px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-input)', color: 'var(--text-primary)', width: 110 }} />
        <button onClick={handleMkdir} disabled={!!busy || !mkdirDraft.trim()}
          style={{ fontSize: 12, padding: '5px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-primary)', cursor: 'pointer', color: 'var(--text-primary)' }}>新建</button>
        {busy && <span style={{ fontSize: 12, color: 'var(--accent)' }}>{busy}</span>}
      </div>
      {loading ? <Spinner /> : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: 'var(--bg-tertiary)' }}>
              {['名称', '类型', '大小', '操作'].map((h) => <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {dirs.length === 0 && <tr><td colSpan={4}><Empty msg="空目录" /></td></tr>}
              {dirs.map((d, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-light)', cursor: 'pointer', transition: 'background 0.1s', color: 'var(--text-primary)' }}
                  onClick={() => handlePreview(d)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--hover-bg)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}>
                  <td style={{ padding: '10px 14px', color: d.is_dir ? 'var(--accent)' : 'var(--text-primary)', fontWeight: d.is_dir ? 600 : 400 }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      {d.is_dir ? <FolderIcon size={14} style={{ flexShrink: 0 }} /> : <FileIcon size={14} style={{ flexShrink: 0 }} />}
                      {d.name}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{d.is_dir ? '目录' : '文件'}</td>
                  <td style={{ padding: '10px 14px', color: 'var(--text-secondary)', fontSize: 12 }}>{d.is_dir ? '-' : `${d.size_kb} KB`}</td>
                  <td style={{ padding: '10px 14px' }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => { setRenameTarget({ path: d.path, name: d.name }); setRenameDraft(d.name) }}
                        title="重命名" aria-label="重命名" className="yuan-tip" data-tip="重命名"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent)', fontSize: 12 }}>重命名</button>
                      <button onClick={() => handleDelete(d)}
                        title="删除" aria-label="删除" className="yuan-tip" data-tip="删除"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--danger)', fontSize: 12 }}>删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {renameTarget && (
        <div onClick={() => setRenameTarget(null)} style={{ position: 'fixed', inset: 0, zIndex: 9998, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: 'var(--bg-primary)', borderRadius: 12, padding: 20, minWidth: 320, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>重命名 {renameTarget.name}</div>
            <input value={renameDraft} onChange={(e) => setRenameDraft(e.target.value)} autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setRenameTarget(null) }}
              style={{ width: '100%', boxSizing: 'border-box', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-input)', color: 'var(--text-primary)', fontSize: 13 }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
              <button onClick={() => setRenameTarget(null)} style={{ padding: '7px 16px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 13 }}>取消</button>
              <button onClick={handleRename} style={{ padding: '7px 16px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontSize: 13 }}>确定</button>
            </div>
          </div>
        </div>
      )}
      {preview && (
        <div onClick={() => setPreview(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: '80%', maxWidth: '80%', maxHeight: '85%', background: 'var(--bg-primary)', borderRadius: 12, padding: 24, overflow: 'auto', minWidth: 360, boxShadow: '0 8px 40px var(--shadow-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{preview.name}</span>
              <span onClick={() => setPreview(null)} title="关闭" aria-label="关闭" style={{ cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}><XIcon size={18} /></span>
            </div>
            {preview.type === 'image' && <img src={`data:image/${preview.ext?.replace('.', '')};base64,${preview.data}`} style={{ maxWidth: '100%', borderRadius: 8 }} />}
            {preview.type === 'html' && <HtmlPreview path={preview.path} content={preview.content} name={preview.name} />}
            {preview.type === 'markdown' && <MarkdownPreview content={preview.content} />}
            {preview.type === 'csv' && <CsvPreview content={preview.content} />}
            {preview.type === 'json' && <JsonPreview content={preview.content} />}
            {preview.type === 'media' && <MediaPreview path={preview.path} ext={preview.ext} />}
            {preview.type === 'pdf' && <PdfPreview path={preview.path} />}
            {preview.type === 'text' && <pre style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 16, fontSize: 13, lineHeight: 1.6, overflow: 'auto', maxHeight: '65vh', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)' }}>{preview.content}</pre>}
            {!preview.type && <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>{preview.detail || '无法预览'}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
