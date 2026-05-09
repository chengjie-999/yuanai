import { useState, useEffect, useCallback } from 'react'
import { API_BASE, getToken, batchFetchUrls, checkCrawlRecord, fetchCrawlRecords, readCrawlRecordFile, deleteCrawlRecord } from '../api'

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '80%', background: '#fff', borderRadius: 12, padding: 20, overflow: 'auto', cursor: 'default', minWidth: 500 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#333' }}>{title}</span>
          <span onClick={onClose} style={{ cursor: 'pointer', fontSize: 18, color: '#999', lineHeight: 1 }}>✕</span>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function DataCollectionPage() {
  const [urlsText, setUrlsText] = useState('https://www.baidu.com/\nhttps://www.bilibili.com/')
  const [retype, setRetype] = useState('text')
  const [method, setMethod] = useState('GET')
  const [postBody, setPostBody] = useState('')
  const [cookieSite, setCookieSite] = useState('')
  const [sites, setSites] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [batchResults, setBatchResults] = useState<{ url: string; status: string; preview?: string; detail?: string; record_id?: number }[] | null>(null)
  const [showBatchModal, setShowBatchModal] = useState(false)
  const [parsedData, setParsedData] = useState<{ title?: string; text?: string; links?: { url: string; text: string }[]; error?: string; recordUrl?: string; recordTime?: string; parsed_title?: string; parsed_text?: string; parsed_links?: string } | null>(null)

  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState<{ content?: string; type: string; url?: string; create_time?: string; parsed_title?: string; parsed_text?: string; parsed_links?: string } | null>(null)
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

    const toFetch: string[] = []
    for (const u of urls) {
      const check = await checkCrawlRecord(u)
      if (check.exists) {
        if (!confirm(`"${u}" 已于 ${check.create_time} 爬取过，是否重新抓取？`)) continue
      }
      toFetch.push(u)
    }
    if (toFetch.length === 0) return

    setLoading(true)
    setBatchResults(null)

    const params: any = { urls: toFetch, retype, method }
    if (cookieSite) params.cookie_site = cookieSite
    if (method === 'POST' && postBody.trim()) {
      try { params.data = JSON.parse(postBody) }
      catch { params.data = postBody }
    }

    const data = await batchFetchUrls(params)
    setBatchResults(data.results || [])
    setShowBatchModal(true)
    loadRecords()
    setLoading(false)
  }

  const handleViewRecord = async (r: any) => {
    const file = await readCrawlRecordFile(r.id)
    if (file.type === 'error') { setDetail({ type: 'error', content: '读取失败', url: r.url }); return }
    // 获取解析数据
    let parsed = null
    if (r.parsed_title) {
      try {
        const res = await fetch(`${API_BASE}/spider/save/record/${r.id}`, { headers: { Authorization: `Bearer ${getToken()}` } })
        parsed = await res.json()
      } catch {}
    }
    setDetail({
      ...file,
      url: r.url,
      create_time: r.create_time,
      parsed_title: r.parsed_title,
      parsed_text: parsed?.parsed_text || '',
      parsed_links: parsed?.parsed_links || '[]',
    })
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

      {/* 批量结果弹窗 */}
      {showBatchModal && batchResults && (
        <Modal title={`📋 批量结果（${batchResults.filter((r) => r.status === 'success').length}/${batchResults.length}）`} onClose={() => setShowBatchModal(false)}>
          {batchResults.map((r, i) => (
            <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0', fontSize: 13, display: 'flex', gap: 8 }}>
              <span style={{ flexShrink: 0 }}>{r.status === 'success' ? '✅' : '❌'}</span>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{ color: '#1976d2', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.url}</div>
                {r.status === 'success' ? (
                  <div style={{ color: '#666', fontSize: 12, marginTop: 2, maxHeight: 60, overflow: 'hidden' }}>{r.preview?.slice(0, 500)}</div>
                ) : (
                  <div style={{ color: '#e53935', fontSize: 12, marginTop: 2 }}>{r.detail}</div>
                )}
              </div>
              {r.status === 'success' && (
                <div style={{ display: 'flex', gap: 4, alignItems: 'center', flexShrink: 0 }}>
                  <button onClick={async () => {
                    try {
                      const res = await fetch(`${API_BASE}/spider/request/parse?url=${encodeURIComponent(r.url)}&record_id=${r.record_id || 0}`, {
                        headers: { Authorization: `Bearer ${getToken()}` },
                      })
                      const data = await res.json()
                      data.recordUrl = r.url
                      data.recordTime = new Date().toISOString().slice(0, 19)
                      setParsedData(data)
                    } catch { setParsedData({ error: '解析失败' }) }
                  }} className="btn btn-outline btn-sm" style={{ fontSize: 10, padding: '4px 8px' }}>解析</button>
                </div>
              )}
            </div>
          ))}
          {batchResults.length === 0 && <div style={{ color: '#999', textAlign: 'center', padding: 20 }}>无结果</div>}
        </Modal>
      )}

      {/* 解析结果弹窗 */}
      {parsedData && (
        <Modal title="📄 解析结果" onClose={() => setParsedData(null)}>
          {parsedData.error ? (
            <div style={{ color: '#e53935' }}>{parsedData.error}</div>
          ) : (
            <>
              {parsedData.recordUrl && <div style={{ fontSize: 12, color: '#1976d2', marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{parsedData.recordUrl}</div>}
              <div style={{ marginBottom: 8 }}><strong>标题：</strong>{parsedData.title}</div>
              <div style={{ marginBottom: 8, color: '#555', lineHeight: 1.6, whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto' }}>{parsedData.text}</div>
              {parsedData.links && parsedData.links.length > 0 && (
                <div>
                  <strong>链接（{parsedData.links.length} 个）：</strong>
                  <div style={{ maxHeight: 150, overflow: 'auto', marginTop: 4 }}>
                    {parsedData.links.map((l: any, i: number) => (
                      <div key={i} style={{ fontSize: 12, padding: '2px 0', color: '#1976d2', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.text || l.url}</div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </Modal>
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
              {r.parsed_title && <span style={{ fontSize: 10, color: '#388e3c', flexShrink: 0 }}>已解析</span>}
              <span style={{ fontSize: 11, color: '#999', flexShrink: 0 }}>{r.create_time?.slice(5, 16)}</span>
              <button onClick={() => handleViewRecord(r)} className="btn btn-outline btn-sm" style={{ fontSize: 10, padding: '2px 6px' }}>查看</button>
              {!r.parsed_title && (
                <button onClick={async () => {
                  try {
                    const res = await fetch(`${API_BASE}/spider/request/parse?url=${encodeURIComponent(r.url)}&record_id=${r.id}`, {
                      headers: { Authorization: `Bearer ${getToken()}` },
                    })
                    const data = await res.json()
                    if (!data.error) { loadRecords(); alert('✅ 解析完成') }
                    else { alert('❌ 解析失败: ' + data.error) }
                  } catch { alert('❌ 解析失败') }
                }} className="btn btn-outline btn-sm" style={{ fontSize: 10, padding: '2px 6px' }}>解析</button>
              )}
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

      {/* 历史详情弹窗 */}
      {detail && (
        <div onClick={() => setDetail(null)} style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: '80%', maxHeight: '80%', background: '#fff', borderRadius: 12, padding: 20, overflow: 'auto', cursor: 'default', minWidth: 500 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: '#333', maxWidth: '80%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail.url}</span>
              <span onClick={() => setDetail(null)} style={{ cursor: 'pointer', fontSize: 18, color: '#999', lineHeight: 1 }}>✕</span>
            </div>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>{detail.create_time}</div>
            {detail.parsed_title && (
              <div style={{ marginBottom: 12, padding: 12, background: '#f0faf0', borderRadius: 8, fontSize: 13 }}>
                <div style={{ fontWeight: 600, color: '#2e7d32', marginBottom: 6 }}>📄 解析结果</div>
                <div style={{ marginBottom: 4 }}><strong>标题：</strong>{detail.parsed_title}</div>
                {detail.parsed_text && <div style={{ color: '#555', lineHeight: 1.6, whiteSpace: 'pre-wrap', maxHeight: 150, overflow: 'auto', marginBottom: 4 }}>{detail.parsed_text}</div>}
                {detail.parsed_links && (() => {
                  try { const links = JSON.parse(detail.parsed_links); return links.length > 0 ? <div><strong>链接：</strong>{links.map((l: any, i: number) => <div key={i} style={{ fontSize: 12, color: '#1976d2', padding: '1px 0' }}>{l.text || l.url}</div>)}</div> : null
                  } catch { return null }
                })()}
              </div>
            )}
            {detail.type === 'html' || detail.type === 'json' ? (
              <>
                <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>原始内容：</div>
                <pre style={{ background: '#f5f5f8', borderRadius: 8, padding: 14, fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '60vh', overflow: 'auto' }}>{detail.content || '(无内容)'}</pre>
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>二进制文件</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const selStyle: React.CSSProperties = { padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd', fontSize: 13, outline: 'none', background: '#fff' }
