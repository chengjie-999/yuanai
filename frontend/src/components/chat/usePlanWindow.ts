// 计划面板窗口控制器 — 模块级单例（ChatPage 切页签会卸载，状态不能随组件丢）
//
// 冲突规则（用户拍板）：
// - 打开恒由用户手势（气泡按钮）→ window.open 命名窗，同名复用不堆叠；手机同标签跳转
// - AI 信号（计划工具事件）：已开 → 聚焦+postMessage 刷新；关 + 60s 冷却期 → 忽略；
//   关 + 无冷却 → 「打开面板」按钮脉冲高亮提示（浏览器弹窗拦截，AI 不能无手势开窗）
// - 关闭：用户手动关 → 60s 冷却；计划终态 → 子窗 3s 倒计时自关（autoclose 预告，不冷却）
import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { trackVisit } from '../../api'
import { PLAN_PATH, PLAN_WIN_NAME, PLAN_WIN_FEATURES, PLAN_MSG } from './planWindow'

const COOLDOWN_MS = 60_000
const PULSE_MS = 20_000
const ACK_MS = 1000

let win: Window | null = null
let dismissedUntil = 0      // 用户手动关窗后的冷却截止时间戳
let expectedClose = false   // 子窗 autoclose 预告过的关闭（不触发冷却）
let pulse = false
let snapshot = { pulse: false }
let pollTimer: number | null = null
let pulseTimer: number | null = null
let ackTimer: number | null = null
let acked = false
const listeners = new Set<() => void>()

function setSnapshot() {
  snapshot = { pulse }
  listeners.forEach((l) => l())
}
const subscribe = (l: () => void) => { listeners.add(l); return () => listeners.delete(l) }
const getSnapshot = () => snapshot

function postToPlan(w: Window, action: 'refresh' | 'autoclose') {
  try { w.postMessage({ type: PLAN_MSG, action }, window.location.origin) } catch { /* 忽略 */ }
}

function clearPulse() {
  pulse = false
  if (pulseTimer) { window.clearTimeout(pulseTimer); pulseTimer = null }
  setSnapshot()
}

function stopPoll() {
  if (pollTimer) { window.clearInterval(pollTimer); pollTimer = null }
}

export function usePlanWindow({ isMobile, navigate }: { isMobile: boolean; navigate: NavigateFunction }) {
  const snap = useSyncExternalStore(subscribe, getSnapshot)
  const optsRef = useRef({ isMobile, navigate })
  optsRef.current = { isMobile, navigate }

  const openPanel = useCallback(() => {
    // 只由用户点击调用（手势 → 弹窗不被拦）；手机端同标签回退
    const { isMobile: mobile, navigate: nav } = optsRef.current
    if (mobile) { nav(PLAN_PATH); return }
    clearPulse()
    dismissedUntil = 0
    let w: Window | null = null
    try {
      w = win && !win.closed ? win : window.open(PLAN_PATH, PLAN_WIN_NAME, PLAN_WIN_FEATURES)
    } catch { w = null }
    if (!w) { nav(PLAN_PATH); return }  // 被拦截兜底
    win = w
    acked = false
    if (!pollTimer) {
      pollTimer = window.setInterval(() => {
        if (win?.closed) {
          if (!expectedClose) dismissedUntil = Date.now() + COOLDOWN_MS  // 用户手动关 → 冷却
          win = null; expectedClose = false; stopPoll(); setSnapshot()
        }
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
    setSnapshot()
  }, [])

  const notifyPlanSignal = useCallback(() => {
    // AI 信号：绝不 window.open（弹窗拦截）。已开 → 聚焦+刷新；冷却期 → 忽略；否则脉冲提示
    if (win && !win.closed) {
      win.focus()
      postToPlan(win, 'refresh')
      return
    }
    if (win) { win = null; stopPoll(); }  // 同步收尸（轮询有 ≤1s 延迟）
    if (Date.now() < dismissedUntil) return
    pulse = true
    setSnapshot()
    trackVisit('/panel/plan?action=pulse&source=ai')
    if (pulseTimer) window.clearTimeout(pulseTimer)
    pulseTimer = window.setTimeout(clearPulse, PULSE_MS)
  }, [])

  // 子窗 → 父窗消息：hello 握手 / autoclose 预告
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || e.data?.type !== PLAN_MSG) return
      if (e.data.action === 'hello') {
        acked = true
        if (ackTimer) { window.clearTimeout(ackTimer); ackTimer = null }
      }
      if (e.data.action === 'autoclose') expectedClose = true
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  return { pulse: snap.pulse, openPanel, notifyPlanSignal }
}
