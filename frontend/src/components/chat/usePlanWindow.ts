// 计划面板窗口 — 用户手动开/关（AI 不自动开也不自动关，用户拍板 2026-10-15）
//
// 保留职责：气泡「打开面板」点击 → 命名弹窗（同名复用不堆叠）；手机端同标签回退；
// 弹窗拦截 → navigate 兜底；1s 无 hello 握手 → 强制重载（同源可写）。
// 后台任务状态由聊天页的「后台执行中」指示条轮询展示，点击同样是手动开窗。
import { useCallback, useEffect, useRef } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { trackVisit } from '../../api'
import { PLAN_PATH, PLAN_WIN_NAME, PLAN_WIN_FEATURES, PLAN_MSG } from './planWindow'

const ACK_MS = 1000

let win: Window | null = null
let pollTimer: number | null = null
let ackTimer: number | null = null
let acked = false

function postToPlan(w: Window, action: 'refresh') {
  try { w.postMessage({ type: PLAN_MSG, action }, window.location.origin) } catch { /* 忽略 */ }
}

function stopPoll() {
  if (pollTimer) { window.clearInterval(pollTimer); pollTimer = null }
}

export function usePlanWindow({ isMobile, navigate, onMobileOpen }: {
  isMobile: boolean; navigate: NavigateFunction; onMobileOpen?: () => void
}) {
  const optsRef = useRef({ isMobile, navigate, onMobileOpen })
  optsRef.current = { isMobile, navigate, onMobileOpen }

  const openPanel = useCallback(() => {
    // 只由用户点击调用（手势 → 弹窗不被拦）；手机端改为对话内浮层
    // （2026-10-17：不再整页跳转离开对话——用户要「不影响对话的子页面」）
    const { isMobile: mobile, navigate: nav, onMobileOpen: mobileOpen } = optsRef.current
    if (mobile) { mobileOpen?.(); return }
    let w: Window | null = null
    try {
      w = win && !win.closed ? win : window.open(PLAN_PATH, PLAN_WIN_NAME, PLAN_WIN_FEATURES)
    } catch { w = null }
    if (!w) { nav(PLAN_PATH); return }  // 被拦截兜底
    win = w
    acked = false
    if (!pollTimer) {
      pollTimer = window.setInterval(() => {
        if (win?.closed) { win = null; stopPoll() }
      }, 1000)
    }
    w.focus()
    postToPlan(w, 'refresh')
    // 1s 无 hello 握手（旧窗页面/加载失败）→ 强制重载（同源可写）
    if (ackTimer) window.clearTimeout(ackTimer)
    ackTimer = window.setTimeout(() => {
      if (!acked && win && !win.closed) { try { win.location.href = PLAN_PATH } catch { /* 忽略 */ } }
    }, ACK_MS)
    trackVisit('/panel/plan?action=open&source=bubble')
  }, [])

  // 子窗 → 父窗消息：hello 握手（清 reload 兜底）
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || e.data?.type !== PLAN_MSG) return
      if (e.data.action === 'hello') {
        acked = true
        if (ackTimer) { window.clearTimeout(ackTimer); ackTimer = null }
      }
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  return { openPanel }
}
