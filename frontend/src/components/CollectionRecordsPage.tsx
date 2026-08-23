import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchCrawlRecords,
  fetchCrawlRecordDetail,
  readCrawlRecordFile,
  deleteCrawlRecord,
} from '../api'

// ===== 类型定义（与后端 api/v1/spider/save.py 返回结构对应） =====

interface CrawlRecord {
  id: number
  url: string
  retype: string          // 保存类型：text/json/html/csv/excel/mysql
  file_path: string       // 原始数据文件路径
  preview: string         // 入库时截取的前 2000 字符预览
  result_length: number   // 原始内容字节数
  parsed_title: string | null
  parsed_text: string | null
  parsed_links: string | null // JSON 数组字符串
  create_time: string     // 'YYYY-MM-DD HH:MM:SS'
}

interface CrawlFile {
  type: string            // 'text' | 'json' | 'binary' | 'error'
  content?: string
  data?: string           // 二进制文件的 base64
}

// 文件内容预览截断上限
const PREVIEW_LIMIT = 5000

// ===== 展示辅助函数 =====

// 保存类型 → 展示标签
const retypeLabel = (t: string) =>
  ({ text: 'HTML', json: 'JSON', html: 'HTML', csv: 'CSV', excel: 'Excel', mysql: 'MySQL' } as Record<string, string>)[t] || t.toUpperCase()

// 保存类型 → 标签配色（固定色在明暗主题下均可读）
const retypeColor = (t: string) =>
  ({ text: 'var(--success)', json: 'var(--accent)', html: 'var(--success)', csv: '#d29922', excel: '#d29922', mysql: '#8b5cf6' } as Record<string, string>)[t] || 'var(--text-secondary)'

// 字节数格式化
const formatBytes = (n: number) => {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

// ===== 内联 SVG 图标 =====

const IconGlobe = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
)

const IconFile = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
  </svg>
)

const IconClock = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
  </svg>
)

const IconTrash = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
)

const IconRefresh = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 4v6h-6" /><path d="M1 20v-6h6" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
    <path d="M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </svg>
)

const IconChevron = ({ open }: { open: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
)

const IconBox = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
  </svg>
)

// ===== 页面组件 =====

export default function CollectionRecordsPage() {
  const [records, setRecords] = useState<CrawlRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const limit = 20
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0) // 手动刷新触发

  // 展开详情：当前展开的记录 id、详情数据、文件内容
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const activeId = useRef<number | null>(null) // 防止并发请求串台
  const [detail, setDetail] = useState<CrawlRecord | null>(null)
  const [file, setFile] = useState<CrawlFile | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  // 操作提示（删除成功等，2s 自动消失）
  const [notice, setNotice] = useState('')

  // 加载记录列表（page / reloadKey 变化时触发）
  useEffect(() => {
    const doLoad = async () => {
      setLoading(true)
      setError('')
      try {
        const res = await fetchCrawlRecords(page, limit)
        setRecords(res.records || [])
        setTotal(res.total || 0)
      } catch {
        setError('加载采集记录失败')
      }
      setLoading(false)
    }
    doLoad()
  }, [page, reloadKey])

  // 展开 / 收起详情：并行拉取记录详情 + 原始文件内容
  const toggleDetail = async (id: number) => {
    if (expandedId === id) {
      activeId.current = null
      setExpandedId(null)
      return
    }
    activeId.current = id
    setExpandedId(id)
    setDetail(null)
    setFile(null)
    setDetailError('')
    setDetailLoading(true)
    const [rec, f] = await Promise.all([fetchCrawlRecordDetail(id), readCrawlRecordFile(id)])
    if (activeId.current !== id) return // 已切换/收起，丢弃过期结果
    setDetail(rec)
    setFile(f)
    if (!rec) setDetailError('记录不存在或已被删除')
    setDetailLoading(false)
  }

  // 删除记录：confirm 确认后调用接口，成功后刷新当前页
  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除该采集记录吗？原始文件与解析结果将一并删除，不可恢复。')) return
    const ok = await deleteCrawlRecord(id)
    if (!ok) {
      setNotice('删除失败，请稍后重试')
      setTimeout(() => setNotice(''), 2000)
      return
    }
    setNotice('记录已删除')
    setTimeout(() => setNotice(''), 2000)
    activeId.current = null
    setExpandedId(null)
    setDetail(null)
    // 当前页只剩这一条且还有上一页时回退一页，否则原地刷新
    if (records.length === 1 && page > 1) setPage(page - 1)
    else setReloadKey((k) => k + 1)
  }

  const totalPages = Math.max(1, Math.ceil(total / limit))

  // 记录状态：是否已保存解析结果
  const statusOf = (r: CrawlRecord) => ({
    label: r.parsed_title || r.parsed_text ? '已解析' : '未解析',
    done: !!(r.parsed_title || r.parsed_text),
  })

  // 解析链接数量（parsed_links 为 JSON 数组字符串）
  const linkCountOf = (r: CrawlRecord) => {
    if (!r.parsed_links) return 0
    try {
      const arr = JSON.parse(r.parsed_links)
      return Array.isArray(arr) ? arr.length : 0
    } catch {
      return 0
    }
  }

  // 文件内容预览（JSON 美化 + 截断）
  const buildPreview = () => {
    if (!file) return ''
    if (file.type === 'error') return ''
    let text = file.content || ''
    if (file.type === 'json') {
      try {
        text = JSON.stringify(JSON.parse(text), null, 2)
      } catch {
        /* 非合法 JSON，保持原文 */
      }
    }
    return text
  }
  const rawPreview = buildPreview()
  const truncatedPreview = rawPreview.length > PREVIEW_LIMIT ? rawPreview.slice(0, PREVIEW_LIMIT) + '\n…' : rawPreview

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
      {/* 页头 */}
      <div style={{
        padding: '8px 12px', background: 'var(--header-bg)', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
      }}>
        <Link to="/chat" style={{
          fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
          padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)',
          flexShrink: 0,
        }}>← 返回</Link>
        <span style={{ fontSize: 15, lineHeight: 1, color: 'var(--accent)', display: 'flex' }}><IconFile /></span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>采集记录</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>爬虫保存的历史记录与文件预览</div>
        </div>
      </div>

      {/* 主体 */}
      <div className="cr-body">
        {/* 工具栏 */}
        <div className="cr-toolbar">
          <span className="cr-count">共 {total} 条记录</span>
          <button className="cr-btn" onClick={() => setReloadKey((k) => k + 1)}>
            <IconRefresh /> 刷新
          </button>
        </div>

        {loading ? (
          <div className="cr-center"><div className="cr-spinner" /></div>
        ) : error ? (
          <div className="cr-center">
            <div style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 10 }}>{error}</div>
            <button className="cr-btn" onClick={() => setReloadKey((k) => k + 1)}><IconRefresh /> 重试</button>
          </div>
        ) : records.length === 0 ? (
          /* 空状态 */
          <div className="cr-center">
            <div style={{ color: 'var(--text-muted)' }}><IconBox /></div>
            <div className="cr-empty-title">暂无采集记录</div>
            <div className="cr-empty-hint">采集任务完成后，保存的记录会出现在这里</div>
          </div>
        ) : (
          <>
            {/* 记录列表 */}
            {records.map((r) => {
              const open = expandedId === r.id
              const status = statusOf(r)
              const color = retypeColor(r.retype)
              return (
                <div key={r.id} className={`cr-card${open ? ' cr-card-open' : ''}`}>
                  {/* 行头：点击展开/收起 */}
                  <div className="cr-card-row" onClick={() => toggleDetail(r.id)}>
                    <div className="cr-card-icon" style={{ color }}>
                      {r.retype === 'text' || r.retype === 'html' ? <IconGlobe /> : <IconFile />}
                    </div>
                    <div className="cr-card-main">
                      <div className="cr-card-title">{r.parsed_title || r.url}</div>
                      <div className="cr-card-url">{r.url}</div>
                    </div>
                    <div className="cr-card-meta">
                      <span className="cr-badge" style={{ color }}>{retypeLabel(r.retype)}</span>
                      <span className="cr-status" style={{ color: status.done ? 'var(--success)' : 'var(--text-muted)' }}>{status.label}</span>
                    </div>
                    <div className="cr-card-side">
                      <span className="cr-size">{formatBytes(r.result_length)}</span>
                      <span className="cr-time"><IconClock /> {r.create_time || '—'}</span>
                    </div>
                    <IconChevron open={open} />
                  </div>

                  {/* 详情（展开时） */}
                  {open && (
                    <div className="cr-detail">
                      {detailLoading ? (
                        <div className="cr-center" style={{ padding: 24 }}><div className="cr-spinner" /></div>
                      ) : detail ? (
                        <>
                          {/* 元信息 */}
                          <div className="cr-meta">
                            <div className="cr-meta-item" style={{ gridColumn: '1 / -1' }}>
                              <label>URL</label>
                              <div className="v">
                                <a href={detail.url} target="_blank" rel="noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  style={{ color: 'var(--accent)', textDecoration: 'none', wordBreak: 'break-all' }}>
                                  {detail.url}
                                </a>
                              </div>
                            </div>
                            <div className="cr-meta-item">
                              <label>保存类型</label>
                              <div className="v" style={{ color: color, fontWeight: 600 }}>{retypeLabel(detail.retype)}</div>
                            </div>
                            <div className="cr-meta-item">
                              <label>文件大小</label>
                              <div className="v">{formatBytes(detail.result_length)}</div>
                            </div>
                            <div className="cr-meta-item">
                              <label>采集时间</label>
                              <div className="v">{detail.create_time || '—'}</div>
                            </div>
                            <div className="cr-meta-item">
                              <label>状态</label>
                              <div className="v" style={{ color: statusOf(detail).done ? 'var(--success)' : 'var(--text-muted)' }}>
                                {statusOf(detail).label}
                              </div>
                            </div>
                            <div className="cr-meta-item" style={{ gridColumn: '1 / -1' }}>
                              <label>文件路径</label>
                              <div className="v" style={{ fontFamily: 'monospace', fontSize: 12 }}>{detail.file_path}</div>
                            </div>
                          </div>

                          {/* 解析结果统计（如有） */}
                          {(detail.parsed_title || detail.parsed_text || detail.parsed_links) && (
                            <div className="cr-stats">
                              {detail.parsed_title && <span className="cr-chip">标题：{detail.parsed_title}</span>}
                              {detail.parsed_links && <span className="cr-chip">解析链接 {linkCountOf(detail)} 条</span>}
                              {detail.parsed_text && <span className="cr-chip">解析文本 {detail.parsed_text.length} 字符</span>}
                            </div>
                          )}

                          {/* 文件内容预览 */}
                          <div className="cr-file">
                            <div className="cr-file-head">
                              <span>文件内容预览</span>
                              {file && (file.type === 'text' || file.type === 'json') && (
                                <span className="cr-file-meta">{retypeLabel(detail.retype)} · 最多显示 {PREVIEW_LIMIT} 字符</span>
                              )}
                            </div>
                            {!file ? (
                              <div className="cr-center" style={{ padding: 20 }}><div className="cr-spinner" /></div>
                            ) : file.type === 'binary' ? (
                              <div className="cr-file-err">该文件为二进制格式，不支持文本预览
                                （约 {formatBytes(Math.floor(((file.data || '').length * 3) / 4))}）</div>
                            ) : file.type === 'error' ? (
                              detail.preview ? (
                                <>
                                  <div className="cr-file-err">原始文件读取失败，以下为保存时的预览片段：</div>
                                  <pre className="cr-pre">{detail.preview}</pre>
                                </>
                              ) : (
                                <div className="cr-file-err">文件读取失败：文件不存在或已丢失</div>
                              )
                            ) : (
                              <>
                                <pre className="cr-pre">{truncatedPreview || '（文件内容为空）'}</pre>
                                {rawPreview.length > PREVIEW_LIMIT && (
                                  <div className="cr-trunc-note">内容过长，仅显示前 {PREVIEW_LIMIT} 字符，完整内容已保存在原始文件中</div>
                                )}
                              </>
                            )}
                          </div>

                          {/* 操作区 */}
                          <div className="cr-detail-foot">
                            <button className="cr-btn-del" onClick={() => handleDelete(detail.id)}>
                              <IconTrash /> 删除记录
                            </button>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>删除后原始文件与解析结果将一并清除</span>
                          </div>
                        </>
                      ) : (
                        <div className="cr-center" style={{ padding: 24 }}>
                          <div style={{ color: 'var(--danger)', fontSize: 13 }}>{detailError || '加载详情失败'}</div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {/* 分页 */}
            <div className="cr-pager">
              <button className="cr-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
              <span className="cr-page-info">第 {page} / {totalPages} 页</span>
              <button className="cr-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
            </div>
          </>
        )}
      </div>

      {/* 操作提示浮层 */}
      {notice && <div className="cr-notice">{notice}</div>}

      <style>{`
        .cr-body {
          flex: 1; overflow: auto; max-width: 900px; width: 100%; margin: 0 auto; box-sizing: border-box; padding: 20px;
        }
        .cr-toolbar {
          display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px;
        }
        .cr-count { font-size: 12px; color: var(--text-secondary); }
        .cr-btn {
          display: inline-flex; align-items: center; gap: 5px; font-size: 12px; padding: 5px 12px;
          border: 1px solid var(--border); border-radius: 6px; background: var(--bg-primary);
          color: var(--text-primary); cursor: pointer; transition: background 0.15s;
        }
        .cr-btn:hover:not(:disabled) { background: var(--hover-bg); }
        .cr-btn:disabled { opacity: 0.45; cursor: not-allowed; }
        .cr-center {
          display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
          padding: 60px 20px; text-align: center;
        }
        .cr-empty-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
        .cr-empty-hint { font-size: 12px; color: var(--text-muted); }
        .cr-spinner {
          width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent);
          border-radius: 50%; animation: cr-spin 0.8s linear infinite;
        }
        @keyframes cr-spin { to { transform: rotate(360deg); } }
        .cr-card {
          background: var(--bg-primary); border: 1px solid var(--border); border-radius: 10px;
          margin-bottom: 10px; overflow: hidden; transition: border-color 0.15s;
        }
        .cr-card-open { border-color: var(--accent); }
        .cr-card-row {
          display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer;
          color: var(--text-primary); transition: background 0.1s;
        }
        .cr-card-row:hover { background: var(--hover-bg); }
        .cr-card-icon {
          width: 30px; height: 30px; border-radius: 8px; background: var(--bg-tertiary);
          display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .cr-card-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
        .cr-card-title {
          font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .cr-card-url { font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cr-card-meta { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
        .cr-badge {
          display: inline-flex; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;
          background: var(--bg-tertiary); border: 1px solid currentColor;
        }
        .cr-status { font-size: 11px; }
        .cr-status::before { content: '● '; font-size: 8px; vertical-align: 1px; }
        .cr-card-side { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
        .cr-size { font-size: 11px; color: var(--text-secondary); font-family: monospace; }
        .cr-time { font-size: 11px; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px; }
        .cr-detail {
          border-top: 1px solid var(--border-light); padding: 16px; background: var(--bg-secondary);
          animation: cr-fade 0.2s ease;
        }
        @keyframes cr-fade { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }
        .cr-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; margin-bottom: 14px; }
        .cr-meta-item { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
        .cr-meta-item label { font-size: 11px; color: var(--text-muted); }
        .cr-meta-item .v { font-size: 13px; color: var(--text-primary); word-break: break-all; }
        .cr-stats { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
        .cr-chip {
          font-size: 11px; color: var(--text-secondary); background: var(--bg-tertiary);
          padding: 3px 10px; border-radius: 10px; max-width: 100%;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .cr-file { margin-bottom: 14px; }
        .cr-file-head {
          display: flex; align-items: center; justify-content: space-between; gap: 8px;
          font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;
        }
        .cr-file-meta { font-size: 11px; font-weight: 400; color: var(--text-muted); }
        .cr-pre {
          background: var(--bg-tertiary); border: 1px solid var(--border-light); border-radius: 8px;
          padding: 12px; font-size: 12px; line-height: 1.6; max-height: 50vh; overflow: auto;
          white-space: pre-wrap; word-break: break-all; color: var(--text-primary); margin: 0;
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        }
        .cr-trunc-note { font-size: 11px; color: var(--text-muted); margin-top: 6px; }
        .cr-file-err {
          font-size: 12px; color: var(--text-secondary); background: var(--bg-tertiary);
          border: 1px dashed var(--border); border-radius: 8px; padding: 14px; margin-bottom: 8px;
        }
        .cr-detail-foot {
          display: flex; align-items: center; justify-content: space-between; gap: 10px;
          border-top: 1px solid var(--border-light); padding-top: 12px;
        }
        .cr-btn-del {
          display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 6px;
          border: 1px solid var(--danger); background: transparent; color: var(--danger);
          font-size: 12px; cursor: pointer; transition: all 0.15s;
        }
        .cr-btn-del:hover { background: var(--danger); color: #fff; }
        .cr-pager {
          display: flex; align-items: center; justify-content: center; gap: 14px;
          padding: 16px 0 8px;
        }
        .cr-page-info { font-size: 12px; color: var(--text-secondary); }
        .cr-notice {
          position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
          background: var(--bg-primary); border: 1px solid var(--border);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18); padding: 8px 16px; border-radius: 8px;
          font-size: 13px; color: var(--text-primary); z-index: 1000;
        }
        /* 响应式：窄屏单列 */
        @media (max-width: 800px) {
          .cr-body { padding: 14px; }
          .cr-card-row { flex-wrap: wrap; gap: 8px; padding: 10px 12px; }
          .cr-card-main { flex: 1 1 100%; order: 2; }
          .cr-card-icon { order: 1; }
          .cr-card-meta { order: 3; }
          .cr-card-side { order: 4; }
          .cr-meta { grid-template-columns: 1fr; }
          .cr-detail-foot { flex-direction: column; align-items: flex-start; }
          .cr-pager { flex-wrap: wrap; }
        }
      `}</style>
    </div>
  )
}
