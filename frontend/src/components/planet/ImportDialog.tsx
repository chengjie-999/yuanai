import { useRef, useState } from 'react'
import { importMaps } from '../../api/planet'
import { UploadIcon, XIcon, LoaderIcon } from '../icons'
import { usePlanetJob } from './ConvertProgress'
import JobProgress from './ConvertProgress'

/* 格式徽标（扩展名启发式；服务端会做真实探测并按保真度择优） */
const FMT_META: Record<string, { label: string; color: string }> = {
  html: { label: 'HTML 高保真', color: 'var(--success)' },
  md: { label: 'Markdown', color: 'var(--accent)' },
  xmind: { label: 'XMind', color: '#8b5cf6' },
  mm: { label: 'FreeMind', color: '#8b5cf6' },
  opml: { label: 'OPML', color: '#8b5cf6' },
  emmx: { label: 'emmx 纯文本', color: 'var(--warning)' },
  txt: { label: '纯文本', color: 'var(--text-muted)' },
}

function fmtOf(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  return FMT_META[ext] ? ext : 'txt'
}

export default function ImportDialog({ pid, onClose, onImported }: {
  pid: number
  onClose: () => void
  onImported: () => void
}) {
  const folderRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<{ file: File; path: string }[]>([])
  const [dragging, setDragging] = useState(false)
  const [jobId, setJobId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const job = usePlanetJob(jobId, (j) => {
    if (j.status === 'done') { onImported(); onClose() }
  })

  const addFiles = (files: File[], paths?: string[]) => {
    const list = Array.from(files).map((f, i) => ({
      file: f,
      path: paths && paths[i] ? paths[i] : (f as any).webkitRelativePath || f.name,
    }))
    setItems((prev) => [...prev, ...list])
    setError('')
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dt = e.dataTransfer
    if (dt.items && dt.items.length && (dt.items[0] as any).webkitGetAsEntry) {
      // 递归读取拖入的文件夹/文件，保留相对路径
      const out: { file: File; path: string }[] = []
      let pending = dt.items.length
      const walk = (entry: any, prefix = '') => {
        if (entry.isFile) {
          entry.file((f: File) => {
            out.push({ file: f, path: prefix + entry.name })
            if (--pending === 0) addFiles(out.map((o) => o.file), out.map((o) => o.path))
          })
        } else if (entry.isDirectory) {
          const reader = entry.createReader()
          const readAll = () => reader.readEntries((entries: any[]) => {
            if (!entries.length) { if (--pending === 0) addFiles(out.map((o) => o.file), out.map((o) => o.path)); return }
            pending += entries.length
            entries.forEach((en: any) => walk(en, prefix + entry.name + '/'))
            pending -= entries.length
            if (pending === 0) addFiles(out.map((o) => o.file), out.map((o) => o.path))
            else readAll()
          })
          readAll()
        } else { if (--pending === 0) addFiles(out.map((o) => o.file), out.map((o) => o.path)) }
      }
      Array.from(dt.items).forEach((it: any) => walk(it.webkitGetAsEntry()))
    } else if (dt.files.length) {
      addFiles(Array.from(dt.files))
    }
  }

  const submit = async () => {
    if (!items.length) return
    setSubmitting(true); setError('')
    try {
      const res: any = await importMaps(pid, items.map((i) => i.file), items.map((i) => i.path))
      setJobId(res.job_id)
    } catch (e: any) {
      setError(e.message || '导入失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 300 }} />
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
        width: 480, maxWidth: '92vw', maxHeight: '82vh', overflow: 'auto',
        background: 'var(--bg-primary)', borderRadius: 14, zIndex: 301,
        boxShadow: '0 12px 40px var(--shadow-md)', padding: '20px 22px',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>导入思维导图</h2>
          <button onClick={onClose} className="yuan-tip" data-tip="关闭" aria-label="关闭"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4, display: 'flex', lineHeight: 1 }}>
            <XIcon size={15} />
          </button>
        </div>

        {/* 拖拽区 */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => folderRef.current?.click()}
          style={{
            border: `1.5px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
            borderRadius: 10, padding: '26px 16px', textAlign: 'center',
            cursor: 'pointer', background: dragging ? 'var(--accent-light)' : 'var(--bg-secondary)',
            transition: 'all 0.15s',
          }}>
          <UploadIcon size={22} style={{ color: 'var(--accent)', marginBottom: 6 }} />
          <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>把整个笔记文件夹拖到这里（或点击选择文件夹）</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            支持 .html / .md / .xmind / .mm / .opml / .emmx，同名文件自动择优合并
          </div>
          <input ref={folderRef} type="file" multiple hidden
            onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
          <input ref={fileRef} type="file" multiple hidden
            onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
          <button onClick={(e) => { e.stopPropagation(); fileRef.current?.click() }}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, marginTop: 6 }}>
            选择单个文件
          </button>
        </div>

        {/* 文件清单 */}
        {items.length > 0 && (
          <div style={{ maxHeight: 180, overflow: 'auto', border: '1px solid var(--border-light)', borderRadius: 8 }}>
            {items.map((it, i) => {
              const fmt = fmtOf(it.file.name)
              const meta = FMT_META[fmt]
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: i < items.length - 1 ? '1px solid var(--border-light)' : 'none', fontSize: 12 }}>
                  <span style={{ flex: 1, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {it.path}
                  </span>
                  <span style={{ padding: '1px 8px', borderRadius: 4, fontSize: 11, color: meta.color, background: 'var(--bg-tertiary)', flexShrink: 0 }}>
                    {meta.label}
                  </span>
                  <button onClick={() => setItems((prev) => prev.filter((_, j) => j !== i))}
                    className="yuan-tip" data-tip="移除" aria-label="移除"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, display: 'flex', lineHeight: 1 }}>
                    <XIcon size={11} />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}
        <JobProgress job={job} />

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onClose} className="btn btn-outline btn-sm">取消</button>
          <button onClick={submit} disabled={!items.length || submitting || job?.status === 'running'} className="btn btn-primary btn-sm">
            {submitting || job?.status === 'running' ? <LoaderIcon size={13} style={{ animation: 'spin 0.8s linear infinite' }} /> : '开始导入'}
          </button>
        </div>
      </div>
    </>
  )
}
