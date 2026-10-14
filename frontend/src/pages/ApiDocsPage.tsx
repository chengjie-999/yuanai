import LandingHeader from '../components/LandingHeader'
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
    "model":"deepseek-v4-flash",
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

export default function ApiDocsPage() {
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
    </div>
  )
}
