import { useSyncExternalStore } from 'react'

/* ============================================================
   自动朗读开关（跨组件同步）— 顶部栏喇叭 / 设置页开关 / 聊天页
   共享同一 localStorage 键 'autoRead'：默认开启，仅显式存 '0' 为关
   ============================================================ */

const KEY = 'autoRead'
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

export function getAutoRead(): boolean {
  return localStorage.getItem(KEY) !== '0'
}

/** 切换开关并广播；返回切换后的值 */
export function toggleAutoRead(): boolean {
  const next = !getAutoRead()
  localStorage.setItem(KEY, next ? '1' : '0')
  emit()
  return next
}

/** 订阅式读取：任意一处切换，顶部栏/设置页/聊天页实时同步 */
export function useAutoRead(): boolean {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb) } },
    getAutoRead,
  )
}
