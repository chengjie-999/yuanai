import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchMedicalSpecies,
  searchMedical,
  assessDrugFeasibility,
  type MedicalArticle,
  type MedicalSpecies,
  type FeasibilityResult,
} from '../api/medical'

/* ============================================================
   医学与生命科学页 — 路由级组件（后续挂载到 /chat/agent/medical）
   区块：文献检索 / 物种导航 / 药物可行性评估 / 基因表达分析引导
   零外部依赖：内联样式 + CSS 变量 + 内联 SVG 图标（lucide 风格）
   ============================================================ */

const MEDICAL_COLOR = '#00897b'  // 生命科学 Agent 主题色（frontend/src/config/agents.ts）

/* lucide 风格 stroke 图标路径 */
const ICONS = {
  search: 'M21 21l-4.35-4.35M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0z',
  book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
  flask: 'M10 2v7.5L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 9.5V2M8.5 2h7M7 16h10',
  cell: 'M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
  chart: 'M18 20V10M12 20V4M6 20v-6',
  external: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3',
  arrow: 'M5 12h14M12 5l7 7-7 7',
  loader: 'M21 12a9 9 0 1 1-6.2-8.56',
}

/* 可行性指示灯配色（红黄绿 ↔ 低中高） */
const VERDICT_META: Record<string, { label: string; color: string; desc: string }> = {
  高: { label: '高', color: '#16a34a', desc: '证据充分，可行性高' },
  中: { label: '中', color: '#f59e0b', desc: '证据有限，需谨慎评估' },
  低: { label: '低', color: '#dc2626', desc: '证据不足或风险高' },
}

function SectionTitle({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="medical-section-head">
      <span className="medical-section-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d={icon} />
        </svg>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>{title}</h3>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0', lineHeight: 1.5 }}>{desc}</p>
      </div>
    </div>
  )
}

export default function MedicalPage() {
  /* ---- 文献检索 ---- */
  const [q, setQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [articles, setArticles] = useState<MedicalArticle[]>([])
  const [searchTotal, setSearchTotal] = useState(0)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  /* ---- 物种导航 ---- */
  const [species, setSpecies] = useState<MedicalSpecies[]>([])

  /* ---- 药物可行性评估 ---- */
  const [drug, setDrug] = useState('')
  const [disease, setDisease] = useState('')
  const [assessing, setAssessing] = useState(false)
  const [feasibility, setFeasibility] = useState<FeasibilityResult | null>(null)
  const [assessError, setAssessError] = useState('')

  /* 物种列表加载（仅一次） */
  useEffect(() => {
    fetchMedicalSpecies().then(setSpecies)
  }, [])

  /* ---- 文献检索 ---- */
  const doSearch = async (e?: FormEvent) => {
    e?.preventDefault()
    const keyword = q.trim()
    if (!keyword || searching) return
    setSearching(true)
    setSearchError('')
    setExpanded(new Set())
    try {
      const res = await searchMedical(keyword, 10)
      setArticles(res.articles)
      setSearchTotal(res.total)
    } catch (err: any) {
      // 网络失败 / 后端 502 统一提示
      setArticles([])
      setSearchTotal(0)
      setSearchError('服务器检索失败，可在对话中委派生命科学 Agent 检索')
      console.error('PubMed 检索失败:', err)
    } finally {
      setSearching(false)
    }
  }

  /* 摘要展开/收起 */
  const toggleExpand = (pmid: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(pmid)) next.delete(pmid)
      else next.add(pmid)
      return next
    })
  }

  /* ---- 药物可行性评估 ---- */
  const doAssess = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!drug.trim() || !disease.trim() || assessing) return
    setAssessing(true)
    setAssessError('')
    setFeasibility(null)
    try {
      setFeasibility(await assessDrugFeasibility(drug.trim(), disease.trim()))
    } catch (err: any) {
      setAssessError(err.message || '评估失败，请稍后重试')
      console.error('可行性评估失败:', err)
    } finally {
      setAssessing(false)
    }
  }

  const verdict = feasibility ? VERDICT_META[feasibility.verdict] || VERDICT_META['中'] : null

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
      {/* ============ 页头（仿 AgentAnalysisPage） ============ */}
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0,
        }}>← 返回</Link>
        <span style={{ fontSize: 18, lineHeight: 1 }}>🧬</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: MEDICAL_COLOR }}>医学与生命科学</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>PubMed 文献检索 · 物种导航 · 药物可行性评估</div>
        </div>
      </div>

      {/* ============ 内容区 ============ */}
      <div className="agent-page-body medical-body" style={{ flex: 1, overflow: 'auto', maxWidth: 900, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>

        {/* ---------- 1. 文献检索 ---------- */}
        <section className="medical-section">
          <SectionTitle icon={ICONS.book} title="PubMed 文献检索" desc="检索全球生物医学文献（esearch + efetch，NCBI E-utilities）" />
          <form className="medical-search-row" onSubmit={doSearch}>
            <input
              className="medical-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="输入关键词，如 metformin diabetes、CRISPR gene therapy"
              disabled={searching}
            />
            <button className="medical-btn" type="submit" disabled={searching || !q.trim()}>
              {searching ? '检索中…' : '搜索'}
            </button>
          </form>

          {searchError && (
            <div className="medical-error">{searchError}</div>
          )}

          {!searching && !searchError && articles.length > 0 && (
            <div className="medical-meta">共 {searchTotal} 篇相关文献，显示前 {articles.length} 篇</div>
          )}

          {articles.map((art) => {
            const isExpanded = expanded.has(art.pmid)
            const abstract = art.abstract === '无摘要' ? art.abstract : isExpanded ? art.abstract : art.abstract.length > 220 ? art.abstract.slice(0, 220) + '…' : art.abstract
            return (
              <div key={art.pmid} className="medical-article">
                <a className="medical-article-title" href={art.url} target="_blank" rel="noreferrer">
                  {art.title}
                </a>
                <div className="medical-article-meta">
                  <span>{art.journal}</span>
                  <span>{art.year}</span>
                  <span>PMID: {art.pmid}</span>
                </div>
                {art.authors.length > 0 && (
                  <div className="medical-article-authors">
                    {art.authors.slice(0, 3).join(', ')}{art.authors.length > 3 ? ' et al.' : ''}
                  </div>
                )}
                <div className="medical-article-abstract">{abstract}</div>
                {art.abstract.length > 220 && art.abstract !== '无摘要' && (
                  <button className="medical-text-btn" type="button" onClick={() => toggleExpand(art.pmid)}>
                    {isExpanded ? '收起' : '展开全文'}
                  </button>
                )}
              </div>
            )
          })}

          {!searching && !searchError && articles.length === 0 && (
            <div className="medical-empty">输入关键词开始检索，或到对话中让统筹委派生命科学 Agent 检索</div>
          )}
        </section>

        {/* ---------- 2. 物种导航 ---------- */}
        <section className="medical-section">
          <SectionTitle icon={ICONS.cell} title="物种导航" desc="常用模式生物及其 MeSH 术语（点击后可在对话中限定物种检索）" />
          {species.length === 0 ? (
            <div className="medical-empty">物种列表加载中…</div>
          ) : (
            <div className="medical-chip-grid">
              {species.map((sp) => (
                <span key={sp.mesh} className="medical-chip">
                  <span className="medical-chip-name">{sp.name}</span>
                  <span className="medical-chip-mesh">{sp.mesh}</span>
                </span>
              ))}
            </div>
          )}
        </section>

        {/* ---------- 3. 药物可行性评估 ---------- */}
        <section className="medical-section">
          <SectionTitle icon={ICONS.flask} title="药物可行性评估" desc="输入药物与疾病，AI 综合临床证据、安全性、机制合理性给出可行性判断" />
          <form className="medical-assess-form" onSubmit={doAssess}>
            <div className="medical-assess-inputs">
              <input
                className="medical-input"
                value={drug}
                onChange={(e) => setDrug(e.target.value)}
                placeholder="药物名称，如 二甲双胍"
                disabled={assessing}
              />
              <input
                className="medical-input"
                value={disease}
                onChange={(e) => setDisease(e.target.value)}
                placeholder="疾病/适应症，如 2型糖尿病"
                disabled={assessing}
              />
            </div>
            <button className="medical-btn" type="submit" disabled={assessing || !drug.trim() || !disease.trim()}>
              {assessing ? '评估中…' : '开始评估'}
            </button>
          </form>

          {assessError && <div className="medical-error">{assessError}</div>}

          {feasibility && verdict && (
            <div className="medical-verdict-card">
              {/* 指示灯：红黄绿 ↔ 低中高 */}
              <div className="medical-light-row">
                {(['低', '中', '高'] as const).map((lv) => (
                  <span key={lv} className="medical-light" title={VERDICT_META[lv].desc}>
                    <span
                      className="medical-light-dot"
                      style={{
                        background: feasibility.verdict === lv ? VERDICT_META[lv].color : 'transparent',
                        borderColor: VERDICT_META[lv].color,
                      }}
                    />
                    <span style={{ color: feasibility.verdict === lv ? VERDICT_META[lv].color : 'var(--text-muted)', fontWeight: feasibility.verdict === lv ? 700 : 400 }}>
                      {VERDICT_META[lv].label}
                    </span>
                  </span>
                ))}
                <span className="medical-light-result" style={{ color: verdict.color }}>
                  {drug.trim()} 治疗 {disease.trim()} — {verdict.desc}
                </span>
              </div>

              {/* 置信度 */}
              <div className="medical-confidence">
                <span className="medical-confidence-label">置信度</span>
                <div className="medical-confidence-bar">
                  <div className="medical-confidence-fill" style={{ width: `${feasibility.confidence * 100}%`, background: verdict.color }} />
                </div>
                <span className="medical-confidence-num" style={{ color: verdict.color }}>
                  {Math.round(feasibility.confidence * 100)}%
                </span>
              </div>

              <div className="medical-reason">{feasibility.reason}</div>
              <div className="medical-note">* 评估基于公开文献与模型推断，不构成医疗建议，用药请咨询专业医生</div>
            </div>
          )}
        </section>

        {/* ---------- 4. 基因表达分析引导卡 ---------- */}
        <section className="medical-section medical-guide">
          <SectionTitle icon={ICONS.chart} title="基因表达分析" desc="生物信息学一站式分析，由生命科学 Agent 在对话中执行" />
          <p className="medical-guide-text">
            在对话中直接对统筹 Agent 说「基因表达分析」，生命科学 Agent 将自动执行
            表达分布直方图、小提琴图、火山图、基因聚类热力图等分析，
            结果图表直接出现在聊天中。
          </p>
          <Link to="/chat" className="medical-guide-cta">
            去对话试试
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d={ICONS.arrow} />
            </svg>
          </Link>
        </section>
      </div>

      <style>{`
        /* ============================
           医学与生命科学页样式
           ============================ */
        .medical-section {
          background: var(--bg-secondary);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 18px 20px;
          margin-bottom: 16px;
        }
        .medical-section-head {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          margin-bottom: 14px;
        }
        .medical-section-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 38px; height: 38px;
          border-radius: 10px;
          background: var(--accent-light);
          color: ${MEDICAL_COLOR};
          flex-shrink: 0;
        }

        /* 检索输入行 */
        .medical-search-row {
          display: flex;
          gap: 8px;
        }
        .medical-input {
          flex: 1;
          min-width: 0;
          background: var(--bg-input);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 10px 12px;
          font-size: 13px;
          color: var(--text-primary);
          outline: none;
          transition: border-color 0.15s;
        }
        .medical-input:focus { border-color: ${MEDICAL_COLOR}; }
        .medical-input::placeholder { color: var(--text-muted); }
        .medical-btn {
          background: ${MEDICAL_COLOR};
          color: #fff;
          border: none;
          border-radius: 8px;
          padding: 10px 20px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          white-space: nowrap;
          transition: opacity 0.15s;
        }
        .medical-btn:hover:not(:disabled) { opacity: 0.88; }
        .medical-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .medical-error {
          margin-top: 12px;
          padding: 10px 12px;
          border-radius: 8px;
          background: rgba(220, 38, 38, 0.08);
          border: 1px solid rgba(220, 38, 38, 0.35);
          color: var(--danger);
          font-size: 13px;
          line-height: 1.6;
        }
        .medical-meta {
          margin-top: 12px;
          font-size: 12px;
          color: var(--text-muted);
        }
        .medical-empty {
          padding: 18px 0 6px;
          font-size: 13px;
          color: var(--text-muted);
          text-align: center;
        }

        /* 文献卡片 */
        .medical-article {
          padding: 14px 0;
          border-bottom: 1px solid var(--border-light);
        }
        .medical-article:last-of-type { border-bottom: none; }
        .medical-article-title {
          display: block;
          font-size: 14px;
          font-weight: 600;
          line-height: 1.5;
          color: var(--text-primary);
          text-decoration: none;
          transition: color 0.15s;
        }
        .medical-article-title:hover { color: ${MEDICAL_COLOR}; }
        .medical-article-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 6px;
          font-size: 12px;
          color: var(--text-muted);
        }
        .medical-article-authors {
          margin-top: 4px;
          font-size: 12px;
          color: var(--text-secondary);
        }
        .medical-article-abstract {
          margin-top: 6px;
          font-size: 13px;
          line-height: 1.7;
          color: var(--text-secondary);
          white-space: pre-wrap;
        }
        .medical-text-btn {
          margin-top: 8px;
          background: none;
          border: none;
          padding: 0;
          font-size: 12px;
          color: ${MEDICAL_COLOR};
          cursor: pointer;
        }

        /* 物种 chip */
        .medical-chip-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .medical-chip {
          display: inline-flex;
          align-items: baseline;
          gap: 6px;
          padding: 6px 12px;
          border-radius: 999px;
          border: 1px solid var(--border);
          background: var(--bg-input);
          cursor: default;
        }
        .medical-chip-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
        .medical-chip-mesh { font-size: 11px; color: var(--text-muted); }

        /* 药物评估表单 */
        .medical-assess-form { display: flex; gap: 8px; }
        .medical-assess-inputs { flex: 1; display: flex; gap: 8px; min-width: 0; }

        /* 可行性结果卡 */
        .medical-verdict-card {
          margin-top: 14px;
          padding: 14px 16px;
          border-radius: 10px;
          border: 1px solid var(--border);
          background: var(--bg-input);
        }
        .medical-light-row {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 14px;
        }
        .medical-light {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
        }
        .medical-light-dot {
          width: 14px; height: 14px;
          border-radius: 50%;
          border: 2px solid;
          box-sizing: border-box;
        }
        .medical-light-result { font-size: 14px; font-weight: 700; }
        .medical-confidence {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-top: 12px;
          font-size: 12px;
          color: var(--text-muted);
        }
        .medical-confidence-bar {
          flex: 1;
          height: 6px;
          border-radius: 3px;
          background: var(--bg-tertiary);
          overflow: hidden;
        }
        .medical-confidence-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
        .medical-confidence-num { font-weight: 700; min-width: 36px; text-align: right; }
        .medical-reason {
          margin-top: 12px;
          font-size: 13px;
          line-height: 1.8;
          color: var(--text-secondary);
          white-space: pre-wrap;
        }
        .medical-note {
          margin-top: 10px;
          font-size: 11px;
          color: var(--text-muted);
        }

        /* 基因表达引导卡 */
        .medical-guide { text-align: left; }
        .medical-guide-text {
          margin: 0 0 14px;
          font-size: 13px;
          line-height: 1.8;
          color: var(--text-secondary);
        }
        .medical-guide-cta {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: ${MEDICAL_COLOR};
          color: #fff;
          font-size: 13px;
          font-weight: 600;
          text-decoration: none;
          padding: 10px 18px;
          border-radius: 8px;
          transition: opacity 0.15s;
        }
        .medical-guide-cta:hover { opacity: 0.88; }

        /* ============================
           响应式：移动端单列
           ============================ */
        @media (max-width: 800px) {
          .medical-section { padding: 14px 12px; }
          .medical-search-row,
          .medical-assess-form { flex-direction: column; }
          .medical-assess-inputs { flex-direction: column; }
          .medical-btn { width: 100%; }
          .medical-light-row { gap: 10px; }
          .medical-light-result { width: 100%; }
        }
      `}</style>
    </div>
  )
}
