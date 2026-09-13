import { useEffect, useState } from 'react'
import { listMaps, listNotes, searchPlanet } from '../../api/planet'
import { GalaxyIcon, StarIcon, RingPlanetIcon, MoonIcon, PlusIcon, ChevronDownIcon, ChevronRightIcon, SearchIcon, RefreshIcon, UploadIcon, TrashIcon } from '../icons'

export interface PlanetRow { id: number; name: string; description: string; map_count: number; note_count: number }
export interface MapRow { id: number; planet_id: number; title: string; quality: string; status: string; note_id: number | null }
export interface NoteRow { id: number; planet_id: number; map_id: number | null; title: string; source: string }

/* 左栏三级树：星球 → 导图 → 笔记 + 检索 + 建星/导入/删除 */
export default function PlanetTree({ planets, selectedPid, selectedMid, selectedNoteId,
  onSelectPlanet, onSelectMap, onSelectNote, onCreatePlanet, onImport, onDeletePlanet, onDeleteMap, onRefresh }: {
    planets: PlanetRow[]
    selectedPid: number | null
    selectedMid: number | null
    selectedNoteId: number | null
    onSelectPlanet: (pid: number) => void
    onSelectMap: (mid: number) => void
    onSelectNote: (nid: number) => void
    onCreatePlanet: () => void
    onImport: (pid: number) => void
    onDeletePlanet: (pid: number) => void
    onDeleteMap: (mid: number) => void
    onRefresh: () => void
  }) {
  const [openPlanets, setOpenPlanets] = useState<Set<number>>(new Set())
  const [mapsCache, setMapsCache] = useState<Record<number, MapRow[]>>({})
  const [notesCache, setNotesCache] = useState<Record<number, NoteRow[]>>({})
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<any[]>([])
  const [searching, setSearching] = useState(false)

  const loadPlanet = async (pid: number) => {
    try {
      const [maps, notes] = await Promise.all([listMaps(pid), listNotes(pid)])
      setMapsCache((p) => ({ ...p, [pid]: maps }))
      setNotesCache((p) => ({ ...p, [pid]: notes }))
    } catch { /* 忽略 */ }
  }

  useEffect(() => {
    // 选中的星球自动展开并加载内容
    if (selectedPid) {
      setOpenPlanets((p) => new Set(p).add(selectedPid!))
      loadPlanet(selectedPid)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPid])

  const doSearch = async () => {
    if (!query.trim()) { setHits([]); return }
    setSearching(true)
    try { setHits(await searchPlanet(query.trim(), selectedPid || 0)) } catch { setHits([]) }
    setSearching(false)
  }

  const noteOfMap = (pid: number, mid: number) => (notesCache[pid] || []).filter((n) => n.map_id === mid)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8 }}>
      {/* 检索 */}
      <div style={{ display: 'flex', gap: 6 }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && doSearch()}
          placeholder="搜索知识星球..."
          style={{ flex: 1, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, outline: 'none', background: 'var(--bg-input)', color: 'var(--text-primary)' }} />
        <button onClick={doSearch} disabled={searching} title={searching ? '搜索中...' : '搜索'} aria-label={searching ? '搜索中...' : '搜索'}
          style={{ padding: '6px 10px', borderRadius: 8, border: 'none', background: 'var(--accent)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}>
          <SearchIcon size={13} />
        </button>
      </div>

      {query.trim() ? (
        /* 检索结果 */
        <div style={{ flex: 1, overflow: 'auto' }}>
          {hits.length === 0 && !searching && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>无匹配结果</div>
          )}
          {hits.map((h, i) => {
            // source = planet:{uid}:{pid}:{mid}[:note] → 跳转到对应星球/导图
            const parts = h.source.split(':')
            const pid = parts.length >= 3 ? Number(parts[2]) : 0
            const mid = parts.length >= 4 ? Number(parts[3]) : 0
            return (
              <div key={i} style={{ padding: '8px 10px', borderBottom: '1px solid var(--border-light)', cursor: 'pointer' }}
                onClick={() => { if (mid) onSelectMap(mid); else if (pid) onSelectPlanet(pid) }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--hover-bg)')}
                onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}>
                <div style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 3 }}>{h.path || h.title}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{h.text}</div>
              </div>
            )
          })}
        </div>
      ) : (
        <>
          {/* 建星 + 刷新 */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={onCreatePlanet}
              style={{ flex: 1, padding: '7px 0', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-input)', cursor: 'pointer', fontSize: 13, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, lineHeight: 1 }}>
              <PlusIcon size={14} /> 新星球
            </button>
            <button onClick={onRefresh} className="yuan-tip" data-tip="刷新" aria-label="刷新"
              style={{ padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-input)', cursor: 'pointer', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1 }}>
              <RefreshIcon size={14} />
            </button>
          </div>

          {/* 星球树 */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            {planets.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 24, lineHeight: 1.8 }}>
                还没有星球<br />新建一个，或直接导入文件夹自动归星
              </div>
            )}
            {planets.map((p) => {
              const open = openPlanets.has(p.id)
              const maps = mapsCache[p.id] || []
              return (
                <div key={p.id}>
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
                    background: selectedPid === p.id ? 'var(--accent-light)' : 'transparent',
                    fontWeight: selectedPid === p.id ? 600 : 400,
                  }}
                    onClick={() => {
                      if (open) setOpenPlanets((s) => { const n = new Set(s); n.delete(p.id); return n })
                      else { setOpenPlanets((s) => new Set(s).add(p.id)); loadPlanet(p.id) }
                      onSelectPlanet(p.id)
                    }}
                    onMouseEnter={(e) => { if (selectedPid !== p.id) (e.currentTarget as HTMLElement).style.background = 'var(--hover-bg)' }}
                    onMouseLeave={(e) => { if (selectedPid !== p.id) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                  >
                    {open ? <ChevronDownIcon size={12} /> : <ChevronRightIcon size={12} />}
                    <GalaxyIcon size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.name}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>{p.map_count}</span>
                    <button onClick={(e) => { e.stopPropagation(); onImport(p.id) }} className="yuan-tip" data-tip="导入导图" aria-label="导入导图"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent)', padding: 2, display: 'flex', lineHeight: 1 }}>
                      <UploadIcon size={13} />
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); onDeletePlanet(p.id) }} className="yuan-tip" data-tip="删除星球" aria-label="删除星球"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, display: 'flex', lineHeight: 1 }}
                      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--danger)')}
                      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}>
                      <TrashIcon size={13} />
                    </button>
                  </div>
                  {open && (
                    <div style={{ paddingLeft: 14 }}>
                      {maps.map((m) => {
                        const notes = noteOfMap(p.id, m.id)
                        return (
                          <div key={m.id}>
                            <div style={{
                              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
                              background: selectedMid === m.id ? 'var(--accent-light)' : 'transparent',
                            }}
                              onClick={() => onSelectMap(m.id)}
                              onMouseEnter={(e) => { if (selectedMid !== m.id) (e.currentTarget as HTMLElement).style.background = 'var(--hover-bg)' }}
                              onMouseLeave={(e) => { if (selectedMid !== m.id) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                            >
                              <StarIcon size={13} style={{ color: 'var(--warning, #f5a623)', flexShrink: 0 }} />
                              <span style={{ flex: 1, fontSize: 13, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.title}</span>
                              <span style={{ fontSize: 10, color: m.quality === 'full' ? 'var(--success)' : 'var(--text-muted)', flexShrink: 0 }}>
                                {m.quality === 'full' ? '完整' : '纯文本'}
                              </span>
                              <button onClick={(e) => { e.stopPropagation(); onDeleteMap(m.id) }} className="yuan-tip" data-tip="删除导图" aria-label="删除导图"
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 2, display: 'flex', lineHeight: 1 }}
                                onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--danger)')}
                                onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}>
                                <TrashIcon size={12} />
                              </button>
                            </div>
                            {notes.map((n) => (
                              <div key={n.id} style={{
                                display: 'flex', alignItems: 'center', gap: 6, padding: '5px 8px 5px 26px', borderRadius: 8, cursor: 'pointer',
                                background: selectedNoteId === n.id ? 'var(--accent-light)' : 'transparent',
                              }}
                                onClick={() => onSelectNote(n.id)}
                                onMouseEnter={(e) => { if (selectedNoteId !== n.id) (e.currentTarget as HTMLElement).style.background = 'var(--hover-bg)' }}
                                onMouseLeave={(e) => { if (selectedNoteId !== n.id) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                              >
                                {n.source === 'user'
                                  ? <MoonIcon size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                  : <RingPlanetIcon size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />}
                                <span style={{ flex: 1, fontSize: 12.5, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.title}</span>
                                {n.source === 'user' && <span style={{ fontSize: 10, color: 'var(--accent)', flexShrink: 0 }}>手改</span>}
                              </div>
                            ))}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
