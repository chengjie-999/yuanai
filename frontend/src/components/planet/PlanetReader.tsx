import { useEffect, useState } from 'react'
import { getMapTree, mapOriginUrl } from '../../api/planet'
import MarkdownContent from '../MarkdownContent'
import { WandIcon, NoteIcon, ChevronRightIcon, LoaderIcon, EditIcon } from '../icons'
import PlanetOutline from './PlanetOutline'
import PlanetMapView from './PlanetMapView'
import NoteEditor from './NoteEditor'
import JobProgress from './ConvertProgress'

export interface MapDetail {
  id: number; planet_id: number; title: string; source_format: string
  node_count: number; max_depth: number; quality: string; warnings: string[]
  note_id: number | null; status: string; error: string
}

type Tab = 'note' | 'map' | 'outline'

/* 右栏阅读器：Tab（笔记 / 导图 / 大纲）+ AI 生成笔记 + 编辑 */
export default function PlanetReader({ map, note, job, onConvert, onSaveNote, onNoteChanged }: {
  map: MapDetail
  note: { id: number; content: string; title: string; source: string } | null
  job: any
  onConvert: (mid: number) => void
  onSaveNote: (nid: number, content: string) => Promise<void>
  onNoteChanged: () => void
}) {
  const [tab, setTab] = useState<Tab>('note')
  const [tree, setTree] = useState<any>(null)
  const [editing, setEditing] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')

  useEffect(() => {
    setEditing(false)
    setSavedMsg('')
    if (map.note_id) setTab('note')
    setTree(null)
  }, [map.id])

  useEffect(() => {
    if (tab !== 'note' && !tree) {
      getMapTree(map.id).then(setTree).catch(() => setTree(null))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, tree, map.id])

  const tabs: { key: Tab; label: string }[] = [
    { key: 'note', label: '笔记' },
    { key: 'map', label: '导图' },
    { key: 'outline', label: '大纲' },
  ]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 头部：标题 + 质量徽标 + AI 生成 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 10, borderBottom: '1px solid var(--border)', flexShrink: 0, flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', margin: 0, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {map.title}
        </h2>
        <span style={{
          fontSize: 11, padding: '2px 10px', borderRadius: 10, flexShrink: 0,
          background: map.quality === 'full' ? 'var(--accent-light)' : 'var(--bg-tertiary)',
          color: map.quality === 'full' ? 'var(--accent)' : 'var(--text-muted)',
        }}>
          {map.quality === 'full' ? '完整层级' : map.quality === 'text-only' ? '纯文本（层级已丢失）' : '平铺文本'}
          {map.node_count ? ` · ${map.node_count} 节点` : ''}
        </span>
        <button onClick={() => onConvert(map.id)} disabled={map.status === 'converting' || job?.status === 'running'}
          style={{
            padding: '7px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', gap: 6, lineHeight: 1,
            opacity: map.status === 'converting' || job?.status === 'running' ? 0.6 : 1,
          }}
          className="yuan-tip" data-tip={map.status === 'converting' ? '转换中...' : '把导图重写为一篇线性文章'} aria-label="AI 生成笔记">
          {map.status === 'converting' || job?.status === 'running'
            ? <LoaderIcon size={14} style={{ animation: 'spin 0.8s linear infinite' }} />
            : <WandIcon size={14} />}
          AI 生成笔记
        </button>
      </div>

      <JobProgress job={job} />

      {map.error && map.status === 'failed' && (
        <div style={{ fontSize: 12, color: 'var(--danger)', padding: '6px 0' }}>转换失败：{map.error}</div>
      )}

      {/* Tab 行 */}
      <div style={{ display: 'flex', gap: 4, padding: '10px 0', flexShrink: 0 }}>
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{
              padding: '5px 14px', borderRadius: 16, border: tab === t.key ? '1px solid var(--accent)' : '1px solid var(--border)',
              background: tab === t.key ? 'var(--accent-light)' : 'transparent', cursor: 'pointer',
              color: tab === t.key ? 'var(--accent)' : 'var(--text-secondary)', fontSize: 12.5, fontWeight: tab === t.key ? 600 : 400,
              transition: 'all 0.15s',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* 内容区 */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {tab === 'note' && (
          editing && note ? (
            <NoteEditor initial={note.content}
              onSave={async (content) => { await onSaveNote(note.id, content); setSavedMsg('已保存'); setTimeout(() => setSavedMsg(''), 2000); onNoteChanged() }}
              onCancel={() => setEditing(false)} />
          ) : note ? (
            <div>
              {savedMsg && <div style={{ fontSize: 12, color: 'var(--success)', marginBottom: 6 }}>{savedMsg}</div>}
              <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', background: 'var(--bg-primary)' }}>
                <MarkdownContent content={note.content} indent />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                <button onClick={() => setEditing(true)}
                  style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 12.5, padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 5 }}>
                  <EditIcon size={13} /> 编辑
                </button>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--text-muted)' }}>
              <NoteIcon size={36} style={{ opacity: 0.35, marginBottom: 10 }} />
              <div style={{ fontSize: 14, marginBottom: 6 }}>还没有笔记</div>
              <div style={{ fontSize: 12, lineHeight: 1.7, marginBottom: 14 }}>
                点击右上角「AI 生成笔记」，把这张导图重写为一篇连贯的线性文章
              </div>
              <button onClick={() => onConvert(map.id)} className="btn btn-primary btn-sm">AI 生成笔记</button>
            </div>
          )
        )}

        {tab === 'outline' && (
          tree ? <PlanetOutline tree={tree} /> : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', padding: 30, color: 'var(--text-muted)', fontSize: 13 }}>
              <LoaderIcon size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> 加载中...
            </div>
          )
        )}

        {tab === 'map' && (
          map.source_format === 'html' ? (
            /* 万兴 html 导出 = 自包含交互页面（原布局/配色/图片），直接渲染原文件 */
            <iframe src={mapOriginUrl(map.id)} title="导图原文件"
              style={{ width: '100%', height: '100%', border: 'none', borderRadius: 8, background: '#fff' }} />
          ) : tree ? <PlanetMapView tree={tree} /> : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', padding: 30, color: 'var(--text-muted)', fontSize: 13 }}>
              <LoaderIcon size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> 加载中...
            </div>
          )
        )}
      </div>

      {/* 层级提示（text-only 兜底说明） */}
      {map.quality !== 'full' && tab !== 'note' && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 10px', borderTop: '1px solid var(--border)', display: 'flex', gap: 6, alignItems: 'center' }}>
          <ChevronRightIcon size={11} /> 原生 .emmx 无法恢复层级：重新导入同名 .html 导出（万兴脑图）即可获得完整层级
        </div>
      )}
      {map.warnings?.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '4px 10px 8px', borderTop: '1px solid var(--border-light)' }}>
          {map.warnings.map((w, i) => <div key={i}>· {w}</div>)}
        </div>
      )}
    </div>
  )
}
