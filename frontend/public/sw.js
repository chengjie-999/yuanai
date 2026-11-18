/* 小元AI Service Worker（T17 PWA，2026-11-18）——最小壳，三条硬规则：
 *
 * 1. /api/ /downloads /docs /api-docs /share 等动态请求【永不缓存】
 *    ——绝不 respondWith，走默认网络（缓存错 API 响应 = 大事故）
 * 2. 只缓存 app shell：index.html（网络优先 + 离线兜底）与 hashed 静态资产
 *    （stale-while-revalidate，文件名带 hash 内容变即失效）
 * 3. 版本化缓存名；不 skipWaiting——新版本等旧页面关闭后下次启动生效
 */

const CACHE = 'xiaoyuan-shell-v1'

// 动态路径前缀黑名单：命中一律不接管（网络直通）
const NEVER_CACHE = ['/api/', '/downloads', '/docs', '/api-docs', '/share/']

function isNeverCache(url) {
  return NEVER_CACHE.some((p) => url.pathname.startsWith(p))
}

// 静态壳资产：同源 + 无查询参数 + 带文件扩展名（hashed 构建产物 / 图标）
function isStaticAsset(url) {
  return url.origin === location.origin
    && /\.[a-z0-9]+$/i.test(url.pathname)
    && !url.search
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.add('/')).catch(() => {})
  )
})

self.addEventListener('activate', (event) => {
  // 清掉旧版本缓存（版本化 CACHE 名变更即全部失效）
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (isNeverCache(url)) return

  // 页面导航：网络优先，离线时回退缓存的壳（数据需联网，壳可看）
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match('/').then((r) => r || caches.match('/index.html'))
      )
    )
    return
  }

  // hashed 静态资产：缓存优先读旧 + 后台刷新（stale-while-revalidate）
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fresh = fetch(req).then((res) => {
          if (res && res.ok) {
            const clone = res.clone()
            caches.open(CACHE).then((cache) => cache.put(req, clone))
          }
          return res
        }).catch(() => cached)
        return cached || fresh
      })
    )
  }
})
