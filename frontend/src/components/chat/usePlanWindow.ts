// 计划面板打开器 — 用户手动开/关（AI 不自动开也不自动关，用户拍板 2026-10-15）
//
// 形态演进：
// - 2026-10-15：桌面=命名弹窗（同名复用不堆叠）/ 移动=同标签整页跳转
// - 2026-10-17 移动端：改为对话内全屏浮层（不离开对话）
// - 2026-10-17 桌面端：改为对话内可拖动浮窗（用户要求「可拖动的子页面」）
// 现在统一为单一出口：onOpen 回调，由 ChatPage 按 isMobile 渲染对应形态。
import { useCallback, useRef } from 'react'

export function usePlanWindow({ onOpen }: { onOpen: () => void }) {
  const optsRef = useRef({ onOpen })
  optsRef.current = { onOpen }

  const openPanel = useCallback(() => {
    // 只由用户点击调用（手势 → 浮层/浮窗不被拦）
    optsRef.current.onOpen()
  }, [])

  return { openPanel }
}
