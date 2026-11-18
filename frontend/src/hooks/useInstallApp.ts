import { useEffect, useState } from 'react'

/** PWA 安装状态与 beforeinstallprompt 捕获（T17，2026-11-18）。
 *
 * 模块级单例存 deferredPrompt（事件对象不能序列化，不走 localStorage）；
 * 监听注册放在模块顶层（首次 import 即生效），组件经 useInstallApp 订阅。
 * iOS Safari 无安装 API——走系统分享引导（适配而非对抗），isIOS 供 UI 分支。
 */

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferred: BeforeInstallPromptEvent | null = null
let installed = false
const subs = new Set<() => void>()

function emit() { subs.forEach((fn) => fn()) }

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()           // 压掉 Chrome 默认横幅，由页面内入口触发
    deferred = e as BeforeInstallPromptEvent
    emit()
  })
  window.addEventListener('appinstalled', () => {
    installed = true
    deferred = null
    emit()
  })
}

export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(display-mode: standalone)').matches
    || (navigator as any).standalone === true   // iOS Safari
}

export function isIOS(): boolean {
  if (typeof navigator === 'undefined') return false
  return /iPad|iPhone|iPod/i.test(navigator.userAgent)
}

export function dismissInstallPrompt() {
  try { localStorage.setItem('pwaInstallDismissed', '1') } catch { /* 忽略 */ }
  emit()
}

export function isInstallDismissed(): boolean {
  try { return localStorage.getItem('pwaInstallDismissed') === '1' } catch { return false }
}

/** 调起系统安装弹窗；返回 'installed' | 'dismissed' | 'unavailable' */
export async function installApp(): Promise<'installed' | 'dismissed' | 'unavailable'> {
  if (!deferred) return 'unavailable'
  try {
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    if (outcome === 'accepted') {
      installed = true
      deferred = null
    }
    emit()
    return outcome === 'accepted' ? 'installed' : 'dismissed'
  } catch {
    return 'unavailable'
  }
}

export interface InstallState {
  /** 当前可用安装入口（Chrome/Edge beforeinstallprompt 已捕获） */
  canInstall: boolean
  /** 已在 standalone 里运行（全屏 App 形态） */
  installed: boolean
  /** iOS 设备（无安装 API，走分享引导） */
  ios: boolean
  /** 用户已拒绝过安装引导（记档不再烦） */
  dismissed: boolean
}

function compute(): InstallState {
  return {
    canInstall: !!deferred && !isStandalone(),
    installed: isStandalone() || installed,
    ios: isIOS(),
    dismissed: isInstallDismissed(),
  }
}

export function useInstallApp(): InstallState & { install: typeof installApp } {
  const [state, setState] = useState<InstallState>(compute)
  useEffect(() => {
    const fn = () => setState(compute())
    subs.add(fn)
    return () => { subs.delete(fn) }
  }, [])
  return { ...state, install: installApp }
}
