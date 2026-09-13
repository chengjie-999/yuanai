import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listPlanets, createPlanet, deletePlanet, getMap, getNote, deleteMap,
  convertMap, saveNote,
} from '../api/planet'
import PlanetTree from '../components/planet/PlanetTree'
import PlanetReader from '../components/planet/PlanetReader'
import ImportDialog from '../components/planet/ImportDialog'
import Starfield from '../components/planet/Starfield'
import { usePlanetJob } from '../components/planet/ConvertProgress'
import { ArrowLeftIcon, GalaxyIcon } from '../components/icons'

/* ============================================================
   知识星球 — /chat/planet（用户个人三级知识库）
   左：星球 → 导图 → 笔记 三级树 + 检索；右：笔记/导图/大纲阅读器
   ============================================================ */

export default function PlanetPage() {
  const [planets, setPlanets] = useState<any[]>([])
  const [selectedPid, setSelectedPid] = useState<number | null>(null)
  const [map, setMap] = useState<any | null>(null)
  const [note, setNote] = useState<any | null>(null)
  const [importPid, setImportPid] = useState<number | null>(null)
  const [jobId, setJobId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')

  const refreshPlanets = useCallback(async () => {
    try { setPlanets(await listPlanets()) } catch (e: any) { setNotice(e.message || '加载失败') }
  }, [])

  useEffect(() => { refreshPlanets() }, [refreshPlanets])

  // 任务完成时刷新列表与当前导图
  const job = usePlanetJob(jobId, async (j: any) => {
    if (j.job_type === 'import' || j.job_type === 'convert') {
      await refreshPlanets()
      if (map) { const m: any = await getMap(map.id); setMap(m); if (m.note_id) loadNote(m.note_id) }
    }
  })

  const loadNote = async (nid: number) => {
    try { setNote(await getNote(nid)) } catch { setNote(null) }
  }

  const handleSelectPlanet = (pid: number) => {
    setSelectedPid(pid)
    setMap(null); setNote(null)
  }

  const handleSelectMap = async (mid: number) => {
    try {
      const m: any = await getMap(mid)
      setMap(m)
      setSelectedPid(m.planet_id)
      if (m.note_id) await loadNote(m.note_id)
      else setNote(null)
    } catch (e: any) { setNotice(e.message || '加载导图失败') }
  }

  const handleSelectNote = async (nid: number) => {
    await loadNote(nid)
  }

  const handleCreatePlanet = async () => {
    const name = window.prompt('星球名称（如「Python 学习」）')
    if (!name?.trim()) return
    try {
      await createPlanet(name.trim())
      await refreshPlanets()
    } catch (e: any) { setNotice(e.message || '创建失败') }
  }

  const handleDeletePlanet = async (pid: number) => {
    const p = planets.find((x) => x.id === pid)
    if (!window.confirm(`删除星球「${p?.name}」？其下所有导图、笔记将一并删除。`)) return
    try {
      await deletePlanet(pid)
      if (selectedPid === pid) { setSelectedPid(null); setMap(null); setNote(null) }
      await refreshPlanets()
    } catch (e: any) { setNotice(e.message || '删除失败') }
  }

  const handleDeleteMap = async (mid: number) => {
    if (!window.confirm('删除这张导图？其笔记将一并删除。')) return
    try {
      await deleteMap(mid)
      if (map?.id === mid) { setMap(null); setNote(null) }
      await refreshPlanets()
    } catch (e: any) { setNotice(e.message || '删除失败') }
  }

  const handleConvert = async (mid: number) => {
    try {
      const res: any = await convertMap(mid)
      setJobId(res.job_id)
      setMap({ ...map, status: 'converting' })
    } catch (e: any) { setNotice(e.message || '启动转换失败') }
  }

  const handleSaveNote = async (nid: number, content: string) => {
    await saveNote(nid, content)
  }

  return (
    <div style={{ height: '100%', position: 'relative', background: 'var(--bg-secondary)' }}>
      {/* 星空背景（Canvas 粒子，明暗自适应） */}
      <Starfield />

      <div style={{ position: 'relative', zIndex: 1, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header（同 Agent 页面模板） */}
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, lineHeight: 1,
        }}><ArrowLeftIcon size={12} /> 返回</Link>
        <span style={{ lineHeight: 1, color: 'var(--accent)', display: 'flex' }}><GalaxyIcon size={19} /></span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>知识星球</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>银河 · 恒星 · 行星 —— 导图一键改写为文章</div>
        </div>
      </div>

      {notice && (
        <div style={{ padding: '6px 16px', fontSize: 12, color: 'var(--danger)', background: 'var(--bg-primary)', borderBottom: '1px solid var(--border)' }}>
          {notice}
        </div>
      )}

      {/* 主体双栏（背景透明，透出星空） */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
        <div style={{
          width: 280, flexShrink: 0, borderRight: '1px solid var(--border)',
          padding: '12px 10px', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <PlanetTree
            planets={planets}
            selectedPid={selectedPid}
            selectedMid={map?.id || null}
            selectedNoteId={note?.id || null}
            onSelectPlanet={handleSelectPlanet}
            onSelectMap={handleSelectMap}
            onSelectNote={handleSelectNote}
            onCreatePlanet={handleCreatePlanet}
            onImport={(pid) => setImportPid(pid)}
            onDeletePlanet={handleDeletePlanet}
            onDeleteMap={handleDeleteMap}
            onRefresh={refreshPlanets}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0, padding: '14px 18px', overflow: 'hidden' }}>
          {map ? (
            <PlanetReader
              map={map}
              note={note}
              job={job}
              onConvert={handleConvert}
              onSaveNote={handleSaveNote}
              onNoteChanged={() => { if (note) loadNote(note.id) }}
            />
          ) : (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, color: 'var(--text-muted)' }}>
              <GalaxyIcon size={46} style={{ opacity: 0.45, color: 'var(--accent)' }} />
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>知识星球</div>
              <div style={{ fontSize: 13, lineHeight: 1.8, textAlign: 'center' }}>
                把万兴脑图的整个文件夹拖进来，自动归星并择优解析<br />
                再用 AI 把导图重写为一篇连贯的线性笔记
              </div>
              {planets.length > 0 && selectedPid && (
                <button onClick={() => setImportPid(selectedPid)} className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>
                  导入导图
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {importPid !== null && (
        <ImportDialog pid={importPid}
          onClose={() => setImportPid(null)}
          onImported={refreshPlanets} />
      )}
      </div>
    </div>
  )
}
