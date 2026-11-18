import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// PWA Service Worker（T17，2026-11-18）：仅生产注册；微信内置浏览器跳过
// （其缓存行为怪异——避让而非对抗）。API 永不进缓存见 public/sw.js；
// updateViaCache:'none' 绕过 HTTP 缓存做更新检查（sw.js 被 nginx 命中
// 30d immutable 也不影响发版更新）。注册失败静默降级，零影响。
if (import.meta.env.PROD && 'serviceWorker' in navigator
  && !/MicroMessenger/i.test(navigator.userAgent)) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {})
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
