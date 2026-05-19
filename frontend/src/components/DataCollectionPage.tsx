import { useState, useEffect, useCallback } from 'react'
import { API_BASE, getToken, fetchCrawlRecords, readCrawlRecordFile, deleteCrawlRecord } from '../api'

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
  const [records, setRecords] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState<{ content?: string; type: string; url?: string; create_time?: string; parsed_title?: string; parsed_text?: string; parsed_links?: string } | null>(null)
  const limit = 10

  const loadRecords = useCallback(async () => {
    const data = await fetchCrawlRecords(page, limit)
    setRecords(data.records || [])
    setTotal(data.total || 0)
  }, [page])

  useEffect(() => { loadRecords() }, [loadRecords])

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
