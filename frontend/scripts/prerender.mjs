/**
 * SEO 预渲染（构建后脚本）：SPA 路由 → 静态 HTML
 *
 * 用法：npm run build && npm run prerender
 * 路由映射：/           → dist/index.html
 *           /api-docs   → dist/docs/index.html（对外路径 /docs）
 *
 * 实现：puppeteer-core + 本机 Edge（不下载 Chromium，国内网络友好）。
 * 本地静态服务带 SPA fallback + /api 反向代理到 localhost:8000——
 * 文档页依赖后端 README 接口，预渲染时经代理拿到真实内容。
 * renderAfterTime 3000ms 等 React 挂载完成（页面已无自定义就绪事件）。
 */
import http from 'node:http'
import { createServer as createStaticServer } from 'node:http'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import puppeteer from 'puppeteer-core'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DIST = join(__dirname, '..', 'dist')
const PORT = 4175
const BACKEND = 'http://localhost:8000'
const RENDER_WAIT_MS = 3000

const ROUTES = [
  { path: '/api-docs', out: 'docs/index.html' },  // 对外路径 /docs
  { path: '/', out: 'index.html' },
]

/* 浏览器可执行文件候选：本地开发用 Edge；Docker 构建用 apk chromium（CHROME_PATH 指定） */
const EDGE_CANDIDATES = [
  process.env.CHROME_PATH,
  process.env.EDGE_PATH,
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/usr/lib/chromium/chrome',
].filter(Boolean)

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
}

/* 静态服务：dist 文件 → SPA fallback(index.html) → /api 代理后端 */
function serve() {
  return createStaticServer(async (req, res) => {
    try {
      const url = new URL(req.url, `http://localhost:${PORT}`)
      if (url.pathname.startsWith('/api/')) {
        // 代理到本地后端（预渲染文档页需要 README 接口）
        const target = BACKEND + url.pathname + url.search
        const upstream = await fetch(target, { headers: req.headers })
        res.writeHead(upstream.status, { 'content-type': upstream.headers.get('content-type') || 'application/json' })
        res.end(Buffer.from(await upstream.arrayBuffer()))
        return
      }
      let p = normalize(decodeURIComponent(url.pathname)).replace(/^([/\\])+/, '')
      if (!p || p === '/') p = 'index.html'
      let fp = join(DIST, p)
      if (!existsSync(fp) || !fp.startsWith(DIST)) {
        fp = join(DIST, 'index.html')  // SPA fallback
      }
      res.writeHead(200, { 'content-type': MIME[extname(fp)] || 'application/octet-stream' })
      res.end(await readFile(fp))
    } catch (e) {
      res.writeHead(500)
      res.end(String(e))
    }
  })
}

async function main() {
  const edge = EDGE_CANDIDATES.find((p) => p && existsSync(p))
  if (!edge) {
    console.error('未找到本机 Edge，请设 EDGE_PATH 指向浏览器可执行文件')
    process.exit(1)
  }
  console.log('使用浏览器:', edge)

  const server = serve()
  await new Promise((r) => server.listen(PORT, r))
  const browser = await puppeteer.launch({
    executablePath: edge,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
  })

  try {
    for (const route of ROUTES) {
      const page = await browser.newPage()
      try {
        await page.goto(`http://localhost:${PORT}${route.path}`, {
          waitUntil: 'networkidle0', timeout: 60000,
        })
        await new Promise((r) => setTimeout(r, RENDER_WAIT_MS))  // React 挂载完成
        const html = await page.content()
        const out = join(DIST, route.out)
        await mkdir(dirname(out), { recursive: true })
        await writeFile(out, html, 'utf-8')
        console.log(`✓ ${route.path} → dist/${route.out}（${(html.length / 1024).toFixed(1)}KB）`)
      } finally {
        await page.close()
      }
    }
  } finally {
    await browser.close()
    server.close()
  }
}

main().catch((e) => {
  console.error('预渲染失败:', e)
  process.exit(1)
})
