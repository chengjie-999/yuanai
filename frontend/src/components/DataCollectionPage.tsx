import { useState, useEffect, useCallback } from 'react'
import { API_BASE, getToken, batchFetchUrls, saveCrawlRecord, fetchCrawlRecords, readCrawlRecordFile, deleteCrawlRecord } from '../api'

export default function DataCollectionPage() {
  const [urlsText, setUrlsText] = useState('https://www.baidu.com/')
  const [retype, setRetype] = useState('text')
  const [method, setMethod] = useState('GET')
  const [postBody, setPostBody] = useState('')
  const [cookieSite, setCookieSite] = useState('')
  const [sites, setSites] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [batchResults, setBatchResults] = useState<{ url: string; status: string; preview?: string; detail?: string }[] | null>(null)

  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState<{ content?: string; type: string; url?: string; create_time?: string } | null>(null)
  const limit = 10

  useEffect(() => {
    const token = getToken()
    if (!token) return
    fetch(`${API_BASE}/spider/request/cookies`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((data) => setSites(data.sites || []))
      .catch(() => {})
  }, [])

  const loadRecords = useCallback(async () => {
    const data = await fetchCrawlRecords(page, limit)
    setRecords(data.records || [])
    setTotal(data.total || 0)
  }, [page])

  useEffect(() => { loadRecords() }, [loadRecords])

  const handleBatch = async () => {
    const urls = urlsText.split('\n').map((u) => u.trim()).filter(Boolean)
    if (urls.length === 0) return

    setLoading(true)
    setBatchResults(null)

    const params: any = { urls, retype, method }
    if (cookieSite) params.cookie_site = cookieSite
    if (method === 'POST' && postBody.trim()) {
      try { params.data = JSON.parse(postBody) }
      catch { params.data = postBody }
    }

    const data = await batchFetchUrls(params)
    setBatchResults(data.results || [])

    // 自动保存到历史
    for (const r of data.results || []) {
      if (r.status === 'success' && r.preview) {
        await saveCrawlRecord(r.url, retype, r.preview)
      }
    }
    loadRecords()
    setLoading(false)
  }

  const handleViewRecord = async (r: any) => {
    const file = await readCrawlRecordFile(r.id)
    if (file.type === 'error') { setDetail({ type: 'error', content: '读取失败' }); return }
    setDetail({ ...file, url: r.url, create_time: r.create_time })
  }

  const handleDeleteRecord = async (id: number) => {
    if (!confirm('删除这条记录？')) return
    if (await deleteCrawlRecord(id)) { setDetail(null); loadRecords() }
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '20px 24px', gap: 12, overflow: 'auto', boxSizing: 'border-box', background: '#f8f9fb' }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0, color: '#2c2c54' }}>📡 数据采集</h2>

      {/* URL 输入区 */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', padding: 12 }}>
        <textarea value={urlsText} onChange={(e) => setUrlsText(e.target.value)}
          placeholder="每行一个 URL..." rows={3}
          style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', resize: 'vertical', boxSizing: 'border-box' }} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
          <select value={retype} onChange={(e) => setRetype(e.target.value)} style={selStyle}>
            <option value="text">文本</option>
            <option value="json">JSON</option>
            <option value="content">二进制</option>
          </select>
          <select value={method} onChange={(e) => setMethod(e.target.value)} style={selStyle}>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
          <select value={cookieSite} onChange={(e) => setCookieSite(e.target.value)} style={selStyle}>
            <option value="">不使用 Cookie</option>
            {sites.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={handleBatch} disabled={loading}
            className="btn btn-primary" style={{ padding: '8px 20px', fontSize: 14, fontWeight: 600, opacity: loading ? 0.6 : 1 }}>
            {loading ? '批量获取中...' : '🔄 批量获取'}
          </button>
        </div>
        {method === 'POST' && (
          <textarea value={postBody} onChange={(e) => setPostBody(e.target.value)}
            placeholder="POST 请求体（JSON格式）" rows={2}
            style={{ width: '100%', padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd', fontSize: 12, outline: 'none', marginTop: 8, fontFamily: 'monospace' }} />
        )}
      </div>

      {/* 批量结果 */}
      {batchResults && batchResults.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
          <div style={{ padding: '8px 14px', background: '#f5f5f8', fontSize: 13, fontWeight: 600, color: '#333', borderBottom: '1px solid #eee' }}>
            📋 批量结果（{batchResults.filter((r) => r.status === 'success').length}/{batchResults.length}）
          </div>
          {batchResults.map((r, i) => (
            <div key={i} style={{ padding: '8px 14px', borderBottom: '1px solid #f5f5f5', fontSize: 13, display: 'flex', gap: 8 }}>
              <span style={{ flexShrink: 0 }}>{r.status === 'success' ? '✅' : '❌'}</span>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{ color: '#1976d2', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.url}</div>
                {r.status === 'success' ? (
                  <div style={{ color: '#666', fontSize: 12, marginTop: 2, maxHeight: 60, overflow: 'hidden' }}>{r.preview?.slice(0, 300)}</div>
                ) : (
                  <div style={{ color: '#e53935', fontSize: 12, marginTop: 2 }}>{r.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 历史记录 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: '#fff', borderRadius: 10, border: '1px solid #eee', overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', background: '#f5f5f8', fontSize: 13, fontWeight: 600, color: '#333', borderBottom: '1px solid #eee' }}>
          📋 爬取历史（{total} 条）
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {records.length === 0 && <div style={{ padding: 30, textAlign: 'center', color: '#ccc', fontSize: 14 }}>暂无记录</div>}
          {records.map((r) => (
            <div key={r.id} style={{ padding: '8px 14px', borderBottom: '1px solid #f5f5f5', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#fafafa'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#1976d2' }}>{r.url}</span>
              <span style={{ fontSize: 11, color: '#999', flexShrink: 0 }}>{r.result_length}字符</span>
              <span style={{ fontSize: 11, color: '#999', flexShrink: 0 }}>{r.create_time?.slice(5, 16)}</span>
              <button onClick={() => handleViewRecord(r)} className="btn btn-outline btn-sm" style={{ fontSize: 10, padding: '2px 6px' }}>查看</button>
              <button onClick={() => handleDeleteRecord(r.id)} className="btn btn-outline-danger btn-sm" style={{ fontSize: 10, padding: '2px 6px' }}>删除</button>
            </div>
          ))}
        </div>
        {totalPages > 1 && (
          <div style={{ padding: '8px 14px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'center', gap: 6, fontSize: 13 }}>
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn btn-outline btn-sm">上一页</button>
            <span style={{ padding: '4px 8px', color: '#999' }}>{page}/{totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="btn btn-outline btn-sm">下一页</button>
          </div>
        )}
      </div>

      {/* 详情弹窗 */}
      {detail && (
        <div onClick={() => setDetail(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '80%', background: '#fff', borderRadius: 12, padding: 20, overflow: 'auto', cursor: 'default', minWidth: 400 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#333', maxWidth: '80%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail.url}</span>
              <span onClick={() => setDetail(null)} style={{ cursor: 'pointer', fontSize: 18, color: '#999', lineHeight: 1 }}>✕</span>
            </div>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>{detail.create_time}</div>
            <pre style={{ background: '#f5f5f8', borderRadius: 8, padding: 14, fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '60vh', overflow: 'auto' }}>{detail.content || '(无内容)'}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

const selStyle: React.CSSProperties = { padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', background: '#fff' }
