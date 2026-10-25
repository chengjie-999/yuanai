import { useSyncExternalStore } from 'react'

/* ============================================================
   回答完成提示音（U5 通用体验 2026-10-25）— 跨组件同步开关，
   同 autoRead 模式：localStorage 键 'answerTone'，默认开启，
   仅显式存 '0' 为关。WebAudio 合成短音，零音频资源文件。
   ============================================================ */

const KEY = 'answerTone'
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

export function getAnswerTone(): boolean {
  try { return localStorage.getItem(KEY) !== '0' } catch { return true }  // 存储受限默认开启
}

/** 切换开关并广播；返回切换后的值 */
export function toggleAnswerTone(): boolean {
  const next = !getAnswerTone()
  try { localStorage.setItem(KEY, next ? '1' : '0') } catch { /* 不落盘仅本次会话 */ }
  emit()
  return next
}

/** 订阅式读取：设置页开关与聊天页联动 */
export function useAnswerTone(): boolean {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb) } },
    getAnswerTone,
  )
}

let _ctx: AudioContext | null = null

/* 合成双音短提示（880Hz→660Hz，各 0.12s）；首次调用需用户手势已解锁
   AudioContext（页面任意点击后即解锁），未解锁/失败静默 */
export function playAnswerTone(): void {
  try {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext
    if (!Ctx) return
    if (!_ctx) _ctx = new Ctx()
    const ctx = _ctx
    if (ctx.state === 'suspended') ctx.resume().catch(() => { /* 无手势未解锁，静默 */ })
    const t0 = ctx.currentTime
    const gain = ctx.createGain()
    gain.connect(ctx.destination)
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(0.12, t0 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.3)
    const osc1 = ctx.createOscillator()
    osc1.type = 'sine'; osc1.frequency.value = 880
    osc1.connect(gain)
    osc1.start(t0); osc1.stop(t0 + 0.14)
    const osc2 = ctx.createOscillator()
    osc2.type = 'sine'; osc2.frequency.value = 660
    osc2.connect(gain)
    osc2.start(t0 + 0.16); osc2.stop(t0 + 0.3)
  } catch { /* 音频不可用静默 */ }
}
