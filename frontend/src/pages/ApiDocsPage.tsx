import { useState, useEffect } from 'react'
import LandingHeader from '../components/LandingHeader'
import MarkdownContent from '../components/MarkdownContent'
import { XIcon, MinusIcon, PlusIcon } from '../components/icons'
import { API_BASE } from '../api'
import { Link } from 'react-router-dom'

/* ============================================================
   API 文档（示例版）— 公开页面 /api-docs
   后续将扩充为完整中文 API 文档；当前覆盖核心示例端点。
   交互式调试走 FastAPI 自带 Swagger（/docs，新标签）。
   ============================================================ */

interface ApiExample {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  title: string
  desc: string
  auth: string
  curl: string
}

const SECTIONS: { group: string; items: ApiExample[] }[] = [
  {
    group: '认证',
    items: [
      {
        method: 'POST', path: '/api/v1/auth/login', title: '登录获取 Token',
        desc: '返回 { token, user }；token 放 Authorization: Bearer 头。登录限流 5 次/60 秒。',
        auth: '公开', curl: `curl -X POST {BASE}/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"你的用户名","password":"你的密码"}'`,
      },
      {
        method: 'GET', path: '/api/v1/auth/memory', title: '读取我的长期记忆',
        desc: '返回 { memory, count, max_items, max_chars }。记忆存 data/.yuan/{uid}/ 文件。',
        auth: 'Bearer', curl: `curl {BASE}/api/v1/auth/memory \\
  -H "Authorization: Bearer <token>"`,
      },
      {
        method: 'DELETE', path: '/api/v1/auth/memory', title: '删除一条记忆',
        desc: '按行文本定位（精确匹配 → 唯一子串），多条命中返回 400 不误删。',
        auth: 'Bearer', curl: `curl -X DELETE {BASE}/api/v1/auth/memory \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{"line":"用户怕辣"}'`,
      },
    ],
  },
  {
    group: '对话（群聊）',
    items: [
      {
        method: 'POST', path: '/api/v1/chat/stream', title: 'SSE 流式对话（主入口）',
        desc: 'history 每条消息带信封字段（sender/recipient/turn/type），模型按身份视图滤波。target_agent 支持 @指定：analysis/collection/automation/claude。',
        auth: 'Bearer', curl: `curl -N {BASE}/api/v1/chat/stream \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model":"deepseek-flash",
    "prompt":"帮我做描述性统计分析",
    "history":[
      {"role":"user","content":"帮我做描述性统计分析",
       "sender":"user","turn":1}
    ],
    "system_prompt":"你是小元AI的统筹助手…",
    "target_agent":"analysis",
    "reasoning_effort":"low"
  }'`,
      },
      {
        method: 'POST', path: '/api/v1/chat/main-session', title: '取/建置顶主对话',
        desc: '豆包式主对话：每用户一条，幂等。登录后前端自动调用并落主对话。',
        auth: 'Bearer', curl: `curl -X POST {BASE}/api/v1/chat/main-session \\
  -H "Authorization: Bearer <token>"`,
      },
      {
        method: 'POST', path: '/api/v1/chat/save', title: '保存会话消息（全量替换）',
        desc: 'session_id + messages 数组。落库后自动触发记忆折叠（fire-and-forget）。',
        auth: 'Bearer', curl: `curl -X POST {BASE}/api/v1/chat/save \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{"session_id":"<sid>","messages":[...],"title":"可选标题"}'`,
      },
    ],
  },
  {
    group: '语音（豆包同款）',
    items: [
      {
        method: 'POST', path: '/api/v1/voice/tts', title: '气泡朗读（流式帧协议）',
        desc: '流式返回帧：kind(1B)+len(4B BE)+payload；0x01 音频 / 0x02 错误 / 0x00 结束。sender 决定音色。',
        auth: 'Bearer', curl: `curl -N {BASE}/api/v1/voice/tts \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"你好，我是小元AI","sender":"orchestrator"}'`,
      },
      {
        method: 'POST', path: '/api/v1/voice/start', title: '实时语音通话',
        desc: '创建 RTC 房间并签发 Token，前端 @volcengine/rtc 进房。未配置 VOICE_* 凭据时 503。',
        auth: 'Bearer', curl: `curl -X POST {BASE}/api/v1/voice/start \\
  -H "Authorization: Bearer <token>"`,
      },
    ],
  },
  {
    group: '知识星球（三级知识库）',
    items: [
      {
        method: 'GET', path: '/api/v1/planet/list', title: '我的星球列表',
        desc: '按登录用户隔离（data/planet/{uid}/）。星球 → 思维导图 → 线性笔记三级结构。',
        auth: 'Bearer', curl: `curl {BASE}/api/v1/planet/list \\
  -H "Authorization: Bearer <token>"`,
      },
      {
        method: 'GET', path: '/api/v1/planet/search', title: '星球知识检索',
        desc: '向量检索用户个人星球内容（Milvus，source=planet:{uid}:… 天然隔离）。',
        auth: 'Bearer', curl: `curl "{BASE}/api/v1/planet/search?q=跨境电商" \\
  -H "Authorization: Bearer <token>"`,
      },
    ],
  },
  {
    group: '数据分析',
    items: [
      {
        method: 'POST', path: '/api/v1/analysis/rfm', title: 'RFM 客户分群',
        desc: '支持 dataset_id 或默认示例文件；结果渲染为交互式 3D 散点大屏。',
        auth: 'Bearer', curl: `curl -X POST {BASE}/api/v1/analysis/rfm \\
  -H "Authorization: Bearer <token>" \\
  -H "Content-Type: application/json" \\
  -d '{}'`,
      },
    ],
  },
]

const METHOD_COLORS: Record<string, string> = {
  GET: '#2e7d32', POST: '#1976d2', PUT: '#e65100', DELETE: '#c62828',
}

/* 图片预览弹层内的按钮统一样式（缩放/1:1/关闭） */
const zoomBtnStyle: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 6, border: '1px solid var(--border)',
  background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: 13, lineHeight: 1, flexShrink: 0,
}

export default function ApiDocsPage() {
  // 项目文档：与仓库 README.md 同一文件（后端 /docs/readme 每次请求读文件，
  // 改 README 即改本页；生产环境 git pull 后自动同步）
  const [readme, setReadme] = useState('')
  const [readmeErr, setReadmeErr] = useState(false)
  useEffect(() => {
    fetch(`${API_BASE}/docs/readme`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => setReadme(t))
      .catch(() => setReadmeErr(true))
  }, [])

  // 图片点击放大（README 里的架构图/ER 图等；小徽章图不放大）；
  // 预览弹层与文件管理同款：面板 + 缩放控制（25%–400%），Esc/点背景关闭
  const [zoomSrc, setZoomSrc] = useState('')
  const [zoom, setZoom] = useState(1)
  useEffect(() => {
    if (!zoomSrc) return
    setZoom(1)
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setZoomSrc('') }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoomSrc])
  const onReadmeClick = (e: React.MouseEvent) => {
    const t = e.target as HTMLElement
    if (t.tagName === 'IMG' && (t as HTMLImageElement).naturalWidth > 120) {
      setZoomSrc((t as HTMLImageElement).src)
    }
  }

  return (
    <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      <LandingHeader />

      <main style={{ flex: 1, width: '100%', maxWidth: 860, margin: '0 auto', padding: '40px 20px 64px' }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, margin: '0 0 6px', color: 'var(--text-primary)' }}>小元AI API 文档</h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', margin: '0 0 28px', lineHeight: 1.7 }}>
          {`BASE = https://你的域名 或 http://localhost:8000`}
          <br />
          认证：JWT（<code>Authorization: Bearer &lt;token&gt;</code>）或 Agent 凭据（<code>X-Agent-Id</code> / <code>X-Agent-Secret</code>，本地 Agent 专用端点）。
          <br />
          限流：登录 5 次/60s · 通用 API 60 次/60s · 上传 10 次/60s。以下为示例版，完整文档与交互式调试见{' '}
          <a href="/docs" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>Swagger（新标签打开）</a>。
        </p>

        {/* 项目文档：README.md 原文实时渲染（同一文件，改 README 即改本页） */}
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 12px', color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
            项目文档（与 README.md 实时同步）
          </h2>
          {readme ? (
            <div className="markdown-body readme-body" onClick={onReadmeClick} style={{
              background: 'var(--bg-input)', border: '1px solid var(--border)',
              borderRadius: 10, padding: '20px 22px', fontSize: 14, lineHeight: 1.7,
            }}>
              <MarkdownContent content={readme} />
            </div>
          ) : (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '14px 2px' }}>
              {readmeErr ? 'README 加载失败（后端未运行或文件缺失）' : '加载中…'}
            </div>
          )}
        </section>

        {SECTIONS.map((s) => (
          <section key={s.group} style={{ marginBottom: 32 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 12px', color: 'var(--text-primary)', borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
              {s.group}
            </h2>
            {s.items.map((item) => (
              <div key={item.method + item.path} style={{
                background: 'var(--bg-input)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '14px 16px', marginBottom: 10,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, color: '#fff', background: METHOD_COLORS[item.method],
                    borderRadius: 4, padding: '2px 7px', letterSpacing: 0.5,
                  }}>{item.method}</span>
                  <code style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{item.path}</code>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.auth}</span>
                </div>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)', margin: '8px 0 4px' }}>
                  {item.title}
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {item.desc}
                </div>
                <pre style={{
                  margin: '10px 0 0', padding: '10px 12px', borderRadius: 8,
                  background: 'var(--bg-primary)', border: '1px solid var(--border-light)',
                  fontSize: 11.5, lineHeight: 1.6, overflowX: 'auto',
                  color: 'var(--text-secondary)', fontFamily: 'Consolas, Monaco, monospace',
                }}>{item.curl}</pre>
              </div>
            ))}
          </section>
        ))}

        <div style={{ marginTop: 24, fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.8 }}>
          更多端点（数据集、知识库、后台管理、Agent 设备等）陆续补充；也可以{' '}
          <Link to="/chat" style={{ color: 'var(--accent)' }}>进入对话</Link> 直接体验对话即执行。
        </div>
      </main>

      {/* 图片放大浮层（文件管理同款弹层 + 缩放控制）：点背景/Esc 关闭 */}
      {zoomSrc && (
        <div onClick={() => setZoomSrc('')} role="presentation" style={{
          position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: '86%', maxWidth: 1100, height: '86%',
            background: 'var(--bg-primary)', borderRadius: 12, overflow: 'hidden',
            boxShadow: '0 8px 40px var(--shadow-md)', display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {zoomSrc.split('/').pop()}
              </span>
              <button onClick={() => setZoom((z) => Math.max(0.25, +(z / 1.25).toFixed(2)))}
                title="缩小" aria-label="缩小" style={zoomBtnStyle}><MinusIcon size={13} /></button>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)', minWidth: 42, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(4, +(z * 1.25).toFixed(2)))}
                title="放大" aria-label="放大" style={zoomBtnStyle}><PlusIcon size={13} /></button>
              <button onClick={() => setZoom(1)} title="恢复原始大小" aria-label="恢复原始大小"
                style={{ ...zoomBtnStyle, fontSize: 11, fontWeight: 600, width: 'auto', padding: '0 8px', color: zoom === 1 ? 'var(--text-muted)' : 'var(--accent)' }}>
                1:1
              </button>
              <button onClick={() => setZoomSrc('')} title="关闭" aria-label="关闭" style={zoomBtnStyle}><XIcon size={16} /></button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 16, background: 'var(--bg-tertiary)' }}>
              <img src={zoomSrc} alt="放大预览" style={{
                width: `${zoom * 100}%`, maxWidth: 'none', borderRadius: 6,
                background: '#fff', display: 'block', margin: '0 auto',
              }} />
            </div>
          </div>
        </div>
      )}

      <style>{`
        .readme-body img { cursor: zoom-in; }
      `}</style>
    </div>
  )
}
