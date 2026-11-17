import { useState, useEffect, useMemo, type ReactNode, type CSSProperties } from 'react'
import LandingHeader from '../components/LandingHeader'
import MarkdownContent from '../components/MarkdownContent'
import ZoomableImage from '../components/chat/ZoomableImage'
import { API_BASE } from '../api'
import { usePageMeta } from '../hooks/usePageMeta'
import { useIsMobile } from '../hooks/useIsMobile'
import { MenuIcon } from '../components/icons'
import { Link, useSearchParams } from 'react-router-dom'

/* ============================================================
   API 文档 — 公开页面 /api-docs
   形态（2026-11-15 用户拍板）：模仿 DeepSeek 官方文档——
   左侧文档树（README 章节 + 用户说明书 + API 参考分组），
   右侧按节渲染（点树换页 + 上一节/下一节），移动端树抽屉化。
   项目文档与仓库 README.md 同一文件（改 README 即改本页）。
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

// ———— README 按 h2 切分（围栏状态机：代码块内的 ## 不算标题） ————
interface ReadmeSection { key: string; title: string; content: string }

function splitReadmeSections(md: string): ReadmeSection[] {
  const sections: ReadmeSection[] = []
  let cur: string[] = []
  let curTitle = '概览'
  let inFence = false
  for (const line of md.split('\n')) {
    if (line.trimStart().startsWith('```')) inFence = !inFence
    if (!inFence && line.startsWith('## ')) {
      sections.push({ key: slug(curTitle), title: curTitle, content: cur.join('\n').trim() })
      curTitle = line.slice(3).trim()
      cur = []
      continue
    }
    cur.push(line)
  }
  sections.push({ key: slug(curTitle), title: curTitle, content: cur.join('\n').trim() })
  return sections
}

function slug(title: string): string {
  return title.replace(/[^\w一-龥-]+/g, '-').replace(/^-+|-+$/g, '') || 'section'
}

// ———— 文档树节点 ————
interface DocNode {
  key: string          // 'readme:<slug>' | 'guide' | 'api:<group>'
  title: string
  children?: DocNode[]
  depth: number
}

export default function ApiDocsPage() {
  usePageMeta({
    title: '小元AI 使用文档 — 快速开始与 API 参考',
    description: '小元AI 使用文档：快速开始、智能体架构、对话界面、计划闭环、长期记忆、API 接口参考与安全说明。',
    ogUrl: 'https://cjyuanai.cn/docs',
    canonical: 'https://cjyuanai.cn/docs',
  })
  const isMobile = useIsMobile()

  // 项目文档：与仓库 README.md 同一文件（改 README 即改本页）
  const [readme, setReadme] = useState('')
  const [readmeErr, setReadmeErr] = useState(false)
  useEffect(() => {
    fetch(`${API_BASE}/docs/readme`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => setReadme(t))
      .catch(() => setReadmeErr(true))
  }, [])

  const readmeSections = useMemo(() => (readme ? splitReadmeSections(readme) : []), [readme])

  // 本地终端使用说明书（docs/terminal-guide.md，白名单端点——用户侧文档）
  const [guide, setGuide] = useState('')
  const [guideErr, setGuideErr] = useState(false)
  useEffect(() => {
    fetch(`${API_BASE}/docs/guide/terminal-guide`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => setGuide(t))
      .catch(() => setGuideErr(true))
  }, [])

  // docs/ 目录文档清单（「用户文档」组——README 里相对链接跳转渲染形态）
  const [docsList, setDocsList] = useState<{ name: string; title: string }[]>([])
  useEffect(() => {
    fetch(`${API_BASE}/docs/list`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setDocsList(Array.isArray(d) ? d : []))
      .catch(() => {})
  }, [])

  // URL 状态（2026-11-15 用户反馈「文档选项没有自己的链接，刷新直接回
  // 概览」）：每个节点独立链接 /api-docs?d=<slug>——刷新保持、可分享
  const [searchParams, setSearchParams] = useSearchParams()

  const keyToSlug = (key: string): string => {
    if (key.startsWith('readme:')) return `readme-${slug(key.slice(7))}`
    if (key.startsWith('doc:')) return `doc-${key.slice(4).replace(/\.md$/, '')}`
    if (key.startsWith('api:')) return `api-${slug(key.slice(4))}`
    return slug(key)
  }

  const slugToKey = (s: string): string | null => {
    if (s.startsWith('readme-')) {
      const title = readmeSections.find((sec) => slug(sec.title) === s.slice(7))?.title
      return title ? `readme:${title}` : null
    }
    if (s.startsWith('doc-')) return `doc:${s.slice(4)}.md`
    if (s.startsWith('api-')) {
      const group = SECTIONS.find((sec) => slug(sec.group) === s.slice(4))?.group
      return group ? `api:${group}` : null
    }
    return null
  }

  // 当前页（URL 驱动：刷新/分享保持；URL 无效回默认概览）
  const [activeKey, setActiveKeyState] = useState<string>('readme:概览')
  const setActiveKey = (key: string) => {
    setActiveKeyState(key)
    setSearchParams(key === 'readme:概览' ? {} : { d: keyToSlug(key) }, { replace: false })
  }
  useEffect(() => {
    // 挂载/readme 加载完成后按 URL 恢复当前文档
    if (!readme) return
    const d = searchParams.get('d')
    if (d) {
      const key = slugToKey(d)
      if (key) setActiveKeyState(key)
    }
  }, [readme])  // eslint-disable-line react-hooks/exhaustive-deps

  const tree: DocNode[] = useMemo(() => {
    const readmeNode: DocNode = {
      key: 'readme-root', title: '项目文档', depth: 0,
      children: readmeSections.map((s) => ({ key: `readme:${s.title}`, title: s.title, depth: 1 })),
    }
    const docsNode: DocNode = {
      key: 'docs-root', title: '用户文档', depth: 0,
      children: docsList.map((d) => ({ key: `doc:${d.name}`, title: d.title, depth: 1 })),
    }
    const apiNode: DocNode = {
      key: 'api-root', title: 'API 参考', depth: 0,
      children: SECTIONS.map((s) => ({ key: `api:${s.group}`, title: s.group, depth: 1 })),
    }
    return [readmeNode, docsNode, apiNode]
  }, [readmeSections, docsList])

  // 平铺顺序（上一节/下一节导航用）
  const flatKeys = useMemo(() => {
    const keys: string[] = []
    readmeSections.forEach((s) => keys.push(`readme:${s.title}`))
    docsList.forEach((d) => keys.push(`doc:${d.name}`))
    SECTIONS.forEach((s) => keys.push(`api:${s.group}`))
    return keys
  }, [readmeSections, docsList])

  const activeIndex = flatKeys.indexOf(activeKey)
  const goPrev = () => { if (activeIndex > 0) setActiveKey(flatKeys[activeIndex - 1]) }
  const goNext = () => { if (activeIndex >= 0 && activeIndex < flatKeys.length - 1) setActiveKey(flatKeys[activeIndex + 1]) }

  // 移动端树抽屉
  const [treeOpen, setTreeOpen] = useState(false)

  // 图片查看：与对话图片同款
  const [zoomSrc, setZoomSrc] = useState('')

  // ———— 当前页内容 ————
  let content: ReactNode = null
  let pageTitle = ''
  if (activeKey === 'guide' || activeKey === 'doc:terminal-guide.md') {
    pageTitle = '本地终端使用说明书'
    content = guide ? (
      <MarkdownContent content={guide} onImageExpand={setZoomSrc} />
    ) : <Loading guideErr={guideErr} />
  } else if (activeKey.startsWith('doc:')) {
    const name = activeKey.slice(4)
    const item = docsList.find((d) => d.name === name)
    pageTitle = item?.title || name
    content = (
      <DocViewer name={name} />
    )
  } else if (activeKey.startsWith('api:')) {
    const group = activeKey.slice(4)
    const sec = SECTIONS.find((s) => s.group === group)
    pageTitle = `API 参考 · ${group}`
    content = sec?.items.map((item) => (
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
    ))
  } else {
    const title = activeKey.slice('readme:'.length)
    const sec = readmeSections.find((s) => s.title === title)
    pageTitle = sec?.title || '项目文档'
    content = readme ? (
      <MarkdownContent content={sec?.content || ''} onImageExpand={setZoomSrc} />
    ) : <Loading guideErr={readmeErr} />
  }

  const renderNode = (node: DocNode) => (
    <div key={node.key}>
      <button
        onClick={() => {
          if (node.children) {
            // 父节点：展开/收起（子节点仍可点）
          }
        }}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, width: '100%', textAlign: 'left',
          padding: node.depth === 0 ? '7px 8px' : '5px 8px 5px 22px',
          border: 'none', background: 'none', cursor: 'pointer', borderRadius: 6,
          fontSize: node.depth === 0 ? 13.5 : 13, fontWeight: node.depth === 0 ? 700 : 400,
          color: 'var(--text-secondary)', transition: 'background 0.12s',
        }}
      >
        {node.depth === 0 ? (node.children?.length ? '▾' : '·') : '·'}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.title}
        </span>
      </button>
      {node.children && (
        <div style={{ paddingLeft: 0 }}>
          {node.children.map((c) => (
            <button
              key={c.key}
              onClick={() => { setActiveKey(c.key); if (isMobile) setTreeOpen(false) }}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '5px 8px 5px 22px', border: 'none', borderRadius: 6,
                background: activeKey === c.key ? 'var(--accent-soft)' : 'none',
                color: activeKey === c.key ? 'var(--accent)' : 'var(--text-secondary)',
                cursor: 'pointer', fontSize: 13, fontWeight: activeKey === c.key ? 600 : 400,
                transition: 'background 0.12s',
              }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                {c.title}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )

  const treeEl = (
    <nav style={{ padding: '10px 8px 24px', overflowY: 'auto', height: '100%' }}>
      {tree.map((n) => renderNode(n))}
    </nav>
  )

  return (
    <div style={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)' }}>
      <LandingHeader />

      <main style={{
        flex: 1, width: '100%', maxWidth: 1080, margin: '0 auto', padding: '20px 20px 64px',
        display: 'flex', gap: 20, alignItems: 'flex-start', position: 'relative',
      }}>
        {/* 左侧文档树（DeepSeek 官方文档同款；移动端抽屉化） */}
        {!isMobile ? (
          <aside style={{
            width: 228, flexShrink: 0, position: 'sticky', top: 20,
            background: 'var(--bg-input)', border: '1px solid var(--border)',
            borderRadius: 10, height: 'calc(100dvh - 40px)', overflow: 'hidden',
          }}>
            {treeEl}
          </aside>
        ) : (
          <>
            <button onClick={() => setTreeOpen(true)} aria-label="打开文档目录"
              style={{
                position: 'fixed', left: 12, top: 74, zIndex: 30,
                padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)',
                background: 'var(--bg-input)', color: 'var(--text-primary)',
                cursor: 'pointer', fontSize: 13,
              }}>
              <MenuIcon size={14} /> 目录
            </button>
            {treeOpen && (
              <>
                <div onClick={() => setTreeOpen(false)} style={{
                  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.4)', zIndex: 39,
                }} />
                <aside style={{
                  position: 'fixed', left: 0, top: 0, bottom: 0, width: 250, zIndex: 40,
                  background: 'var(--bg-input)', borderRight: '1px solid var(--border)',
                  transform: treeOpen ? 'translateX(0)' : 'translateX(-100%)',
                  transition: 'transform 0.2s', overflow: 'hidden',
                }}>
                  {treeEl}
                </aside>
              </>
            )}
          </>
        )}

        {/* 右侧内容区（按节渲染 + 上一节/下一节） */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 14, gap: 10, flexWrap: 'wrap',
          }}>
            <h1 style={{ fontSize: 20, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>{pageTitle}</h1>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={goPrev} disabled={activeIndex <= 0}
                style={navBtnStyle(activeIndex <= 0)}>← 上一节</button>
              <button onClick={goNext} disabled={activeIndex < 0 || activeIndex >= flatKeys.length - 1}
                style={navBtnStyle(activeIndex < 0 || activeIndex >= flatKeys.length - 1)}>下一节 →</button>
            </div>
          </div>
          <div className="markdown-body" style={{
            background: 'var(--bg-input)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '20px 22px', fontSize: 14, lineHeight: 1.7,
            minHeight: 300,
          }}
          onClick={(e) => {
            // 文档内相对链接（后端改写为 /api/v1/docs/asset/xxx.md）→ 站内
            // 渲染视图切换（用户反馈「直接源码可读性太差」）
            const a = (e.target as HTMLElement).closest('a')
            if (!a) return
            const m = a.getAttribute('href')?.match(/\/api\/v1\/docs\/asset\/([\w\-.]+)\.md$/)
            if (m) {
              e.preventDefault()
              setActiveKey(`doc:${m[1]}.md`)
            }
          }}>
            {content}
          </div>
          <div style={{ marginTop: 18, fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.8 }}>
            BASE = https://你的域名 或 http://localhost:8000 · 认证 JWT（Bearer token）或 Agent 凭据（X-Agent-Id/X-Agent-Secret）
            · 限流：登录 5 次/60s · 通用 API 60 次/60s · 上传 10 次/60s
            · 交互式调试见 <a href="/docs" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>Swagger</a>
            · <Link to="/chat" style={{ color: 'var(--accent)' }}>进入对话</Link> 直接体验对话即执行。
          </div>
        </div>
      </main>

      {zoomSrc && <ZoomableImage src={zoomSrc} onClose={() => setZoomSrc('')} />}
    </div>
  )
}

function navBtnStyle(disabled: boolean): CSSProperties {
  return {
    padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)',
    background: 'var(--bg-input)', color: disabled ? 'var(--text-muted)' : 'var(--text-primary)',
    cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 13, opacity: disabled ? 0.55 : 1,
  }
}

function Loading({ guideErr }: { guideErr: boolean }) {
  return (
    <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '14px 2px' }}>
      {guideErr ? '文档加载失败（后端未运行或文件缺失）' : '加载中…'}
    </div>
  )
}

function DocViewer({ name }: { name: string }) {
  const [doc, setDoc] = useState('')
  const [err, setErr] = useState(false)
  useEffect(() => {
    setDoc('')
    setErr(false)
    fetch(`${API_BASE}/docs/guide/${encodeURIComponent(name)}`)
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => setDoc(t))
      .catch(() => setErr(true))
  }, [name])
  const [zoomSrc, setZoomSrc] = useState('')
  if (!doc && !err) return <Loading guideErr={false} />
  if (err) return <Loading guideErr={true} />
  return (
    <>
      <MarkdownContent content={doc} onImageExpand={setZoomSrc} />
      {zoomSrc && <ZoomableImage src={zoomSrc} onClose={() => setZoomSrc('')} />}
    </>
  )
}
