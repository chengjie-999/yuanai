// ============================================================
// 医学与生命科学 API — 物种导航 / PubMed 文献检索 / 药物可行性评估
// 后端: api/v1/medical/router.py（/api/v1/medical 前缀，JWT 保护）
// 2026-10-19 去重：API_BASE/getToken/authHeaders 复用 api/index.ts
// ============================================================

import { API_BASE, authHeaders } from './index'

function jsonHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json', ...authHeaders() }
}

// ---- 类型 ----

export interface MedicalSpecies {
  name: string      // 中文规范名，如 人类 / 小鼠
  mesh: string      // MeSH 术语，如 humans / mice
}

export interface MedicalArticle {
  pmid: string
  title: string
  authors: string[]
  journal: string
  year: string
  abstract: string
  url: string
}

export interface FeasibilityResult {
  verdict: '高' | '中' | '低'
  reason: string
  confidence: number  // 0-1
}

// ---- 物种导航 ----

export async function fetchMedicalSpecies(): Promise<MedicalSpecies[]> {
  try {
    const res = await fetch(`${API_BASE}/medical/species`, { headers: authHeaders() })
    if (!res.ok) return []
    const data = await res.json()
    return data.species || []
  } catch { return [] }
}

// ---- PubMed 文献检索 ----

export async function searchMedical(q: string, max = 10): Promise<{ total: number; articles: MedicalArticle[] }> {
  const res = await fetch(`${API_BASE}/medical/search?q=${encodeURIComponent(q)}&max=${max}`, {
    headers: authHeaders(),
  })
  if (!res.ok) {
    // 后端 502：NCBI 不可达；前端统一提示「服务器检索失败」
    let detail = '检索失败'
    try { detail = (await res.json()).detail || detail } catch { /* 忽略解析失败 */ }
    throw new Error(detail)
  }
  return await res.json()
}

// ---- 药物可行性评估 ----

export async function assessDrugFeasibility(drug: string, disease: string): Promise<FeasibilityResult> {
  const res = await fetch(`${API_BASE}/medical/feasibility`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ drug, disease }),
  })
  if (!res.ok) {
    let detail = '评估失败'
    try { detail = (await res.json()).detail || detail } catch { /* 忽略解析失败 */ }
    throw new Error(detail)
  }
  return await res.json()
}
