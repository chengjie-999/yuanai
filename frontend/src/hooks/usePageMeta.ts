import { useEffect } from 'react'

/* 按路由设置页面元信息（SEO 第 4 步，2026-10-26）：
   title / description / og:* / canonical——运行时改 document 头部，
   预渲染（构建后脚本）抓取时自然带出各路由独立标题与描述。 */

function upsertMeta(attr: 'name' | 'property', key: string, content: string) {
  if (!content) return
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function upsertCanonical(url: string) {
  if (!url) return
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', url)
}

export interface PageMeta {
  title: string
  description: string
  ogTitle?: string
  ogDescription?: string
  ogUrl?: string
  canonical?: string
}

export function usePageMeta(meta: PageMeta) {
  useEffect(() => {
    document.title = meta.title
    upsertMeta('name', 'description', meta.description)
    upsertMeta('property', 'og:title', meta.ogTitle || meta.title)
    upsertMeta('property', 'og:description', meta.ogDescription || meta.description)
    upsertMeta('property', 'og:url', meta.ogUrl || '')
    upsertCanonical(meta.canonical || '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.title, meta.description, meta.ogTitle, meta.ogDescription, meta.ogUrl, meta.canonical])
}
