/* 知识星球 API — 星球/导图/笔记/导入任务/检索 */
import { API_BASE, getToken } from './index'

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function req<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...authHeaders(), ...(init?.headers || {}) } })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return await res.json()
}

/* ---- 星球 ---- */
export function listPlanets() { return req('/planet/list').then((d: any) => d.planets || []) }
export function createPlanet(name: string, description = '') {
  return req('/planet/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description }) })
}
export function updatePlanet(pid: number, patch: { name?: string; description?: string; sort_order?: number }) {
  return req(`/planet/${pid}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })
}
export function deletePlanet(pid: number) { return req(`/planet/${pid}`, { method: 'DELETE' }) }

/* ---- 导图 ---- */
export function listMaps(pid: number) { return req(`/planet/${pid}/maps`).then((d: any) => d.maps || []) }
export function getMap(mid: number) { return req(`/planet/maps/${mid}`).then((d: any) => d.map) }
export function getMapTree(mid: number) { return req(`/planet/maps/${mid}/tree`) }
export async function getMapOutline(mid: number): Promise<string> {
  // 后端返回 markdown 文本（非 JSON），不能用 req 的 res.json()
  const res = await fetch(`${API_BASE}/planet/maps/${mid}/outline`, { headers: authHeaders() })
  if (!res.ok) throw new Error('大纲加载失败')
  return await res.text()
}
export function deleteMap(mid: number) { return req(`/planet/maps/${mid}`, { method: 'DELETE' }) }

/** 批量导入：files 与相对路径平行对齐（webkitdirectory 文件夹） */
export function importMaps(pid: number, files: File[], paths: string[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  paths.forEach((p) => form.append('paths', p))
  return req(`/planet/${pid}/import`, { method: 'POST', body: form })
}

export function convertMap(mid: number) { return req(`/planet/maps/${mid}/convert`, { method: 'POST' }) }

/* ---- 笔记 ---- */
export function listNotes(pid?: number, mid?: number) {
  const q = new URLSearchParams()
  if (pid) q.set('pid', String(pid))
  if (mid) q.set('mid', String(mid))
  return req(`/planet/notes?${q}`).then((d: any) => d.notes || [])
}
export function getNote(nid: number) { return req(`/planet/notes/${nid}`).then((d: any) => d.note) }
export function saveNote(nid: number, content: string, title = '') {
  return req(`/planet/notes/${nid}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, title }) })
}
export function createNote(planetId: number, content: string, title = '') {
  return req('/planet/notes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ planet_id: planetId, content, title }) })
}
export function deleteNote(nid: number) { return req(`/planet/notes/${nid}`, { method: 'DELETE' }) }

/* ---- 任务与检索 ---- */
export function getJob(jid: number) { return req(`/planet/jobs/${jid}`) }
export function searchPlanet(q: string, pid = 0, topK = 5) {
  return req(`/planet/search?q=${encodeURIComponent(q)}${pid ? `&pid=${pid}` : ''}&top_k=${topK}`).then((d: any) => d.results || [])
}

/* 图片资产 URL（<img> 无法带 header，走 ?token=） */
export function planetAssetUrl(pid: number, mid: number, name: string): string {
  return `${API_BASE}/planet/asset/${pid}/${mid}/${encodeURIComponent(name)}?token=${getToken()}`
}

/* 导图原始文件 URL（iframe 无法带 header，走 ?token=；万兴 html 导出为自包含交互页面） */
export function mapOriginUrl(mid: number): string {
  return `${API_BASE}/planet/maps/${mid}/origin?token=${getToken()}`
}
