import { useEffect, useRef } from 'react'

/* ============================================================
   神经元网络背景 — 大脑内部神经元连接（Canvas 零依赖）
   节点=神经元（缓慢漂移，少量 hub 大节点），连线=突触
   （距离越近越亮），信号脉冲亮点沿突触传播。
   主题感知：data-theme 切换即时换调色板（亮=淡蓝灰阶，
   暗=发光蓝紫）；尊重 prefers-reduced-motion（静态一帧）。
   ============================================================ */

interface Neuron { x: number; y: number; vx: number; vy: number; r: number; hub: boolean; tint: number }
interface Pulse { i: number; j: number; t: number; speed: number }

const EDGE_MAX = 150        // 突触最大连接距离（px）
const PULSE_INTERVAL = 240  // 信号发射间隔（ms）
const MAX_PULSES = 5        // 同屏最大脉冲数

// 节点色调：蓝 / 靛 / 天蓝，仿多荧光染色神经元切片
const TINTS_LIGHT = ['96,165,250', '129,140,248', '56,189,248']
const TINTS_DARK = ['96,165,250', '129,140,248', '125,211,252']

export default function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const parent = canvas.parentElement
    if (!parent) return

    const isDark = () => document.documentElement.getAttribute('data-theme') === 'dark'
    // 明暗双套（每帧按主题取，切换无需重启循环）
    const P = () => isDark()
      ? {
          tints: TINTS_DARK, nodeAlpha: 0.55,
          edge: '96,165,250', edgeAlpha: 0.13,
          hub: 'rgba(147,197,253,0.85)', core: 'rgba(239,246,255,0.9)',
          pulse: '#93c5fd', glow: 8,
        }
      : {
          tints: TINTS_LIGHT, nodeAlpha: 0.5,
          edge: '37,99,235', edgeAlpha: 0.10,
          hub: 'rgba(37,99,235,0.5)', core: 'rgba(255,255,255,0.95)',
          pulse: '#2563eb', glow: 0,
        }

    let W = 0, H = 0
    let neurons: Neuron[] = []
    let pairs: [number, number][] = []
    let pulses: Pulse[] = []
    let dpr = 1

    const build = () => {
      const rect = parent.getBoundingClientRect()
      if (rect.width < 4 || rect.height < 4) return
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = rect.width; H = rect.height
      canvas.width = Math.round(W * dpr)
      canvas.height = Math.round(H * dpr)
      canvas.style.width = W + 'px'
      canvas.style.height = H + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      // 按面积布点：约每 20000px² 一个神经元，上限 90 控性能
      const count = Math.max(28, Math.min(90, Math.round((W * H) / 20000)))
      neurons = Array.from({ length: count }, () => {
        const r = Math.random()
        return {
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.28, vy: (Math.random() - 0.5) * 0.28,
          r: 1.3 + Math.random() * 2.3,
          hub: Math.random() < 0.12,
          tint: r < 0.65 ? 0 : r < 0.85 ? 1 : 2,
        }
      })
      // 突触对预计算（节点缓漂，配对固定）
      pairs = []
      for (let i = 0; i < neurons.length; i++)
        for (let j = i + 1; j < neurons.length; j++)
          pairs.push([i, j])
    }

    const draw = () => {
      const p = P()
      ctx.clearRect(0, 0, W, H)

      // 突触连线：距离越近越亮，hub 参与时更亮
      for (const [i, j] of pairs) {
        const a = neurons[i], b = neurons[j]
        const dx = a.x - b.x, dy = a.y - b.y
        const d2 = dx * dx + dy * dy
        if (d2 > EDGE_MAX * EDGE_MAX) continue
        const alpha = (1 - Math.sqrt(d2) / EDGE_MAX) * p.edgeAlpha * (a.hub || b.hub ? 1.6 : 1)
        ctx.strokeStyle = `rgba(${p.edge},${alpha.toFixed(3)})`
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
      }

      // 信号脉冲：亮点沿突触传播，带淡尾迹
      for (const pl of pulses) {
        const a = neurons[pl.i], b = neurons[pl.j]
        const x = a.x + (b.x - a.x) * pl.t
        const y = a.y + (b.y - a.y) * pl.t
        if (p.glow > 0) { ctx.shadowColor = p.pulse; ctx.shadowBlur = p.glow }
        ctx.globalAlpha = 0.5
        ctx.strokeStyle = p.pulse
        ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(x, y); ctx.stroke()
        ctx.globalAlpha = 1
        ctx.fillStyle = p.pulse
        ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill()
        ctx.shadowBlur = 0
      }

      // 神经元节点（hub 亮核）
      for (const n of neurons) {
        ctx.fillStyle = `rgba(${p.tints[n.tint]},${n.hub ? p.nodeAlpha + 0.3 : p.nodeAlpha})`
        if (n.hub && p.glow > 0) { ctx.shadowColor = p.pulse; ctx.shadowBlur = p.glow }
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill()
        ctx.shadowBlur = 0
        if (n.hub) {
          ctx.fillStyle = p.core
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r * 0.45, 0, Math.PI * 2); ctx.fill()
        }
      }
    }

    // ---- 帧循环 ----
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let raf = 0
    let last = performance.now()
    let lastPulse = 0

    const step = (now: number) => {
      const dt = Math.min((now - last) / 16.7, 3)
      last = now
      if (neurons.length) {
        // 神经元缓漂（出界回绕）
        for (const n of neurons) {
          n.x += n.vx * dt; n.y += n.vy * dt
          if (n.x < -20) n.x = W + 20; else if (n.x > W + 20) n.x = -20
          if (n.y < -20) n.y = H + 20; else if (n.y > H + 20) n.y = -20
        }
        // 脉冲推进 + 随机沿在范围内的突触发射
        for (const pl of pulses) pl.t += pl.speed * dt
        pulses = pulses.filter((pl) => pl.t < 1)
        if (now - lastPulse > PULSE_INTERVAL && pulses.length < MAX_PULSES) {
          lastPulse = now
          for (let tries = 0; tries < 12; tries++) {
            const i = Math.floor(Math.random() * neurons.length)
            const j = Math.floor(Math.random() * neurons.length)
            if (i === j) continue
            const dx = neurons[i].x - neurons[j].x, dy = neurons[i].y - neurons[j].y
            if (dx * dx + dy * dy < EDGE_MAX * EDGE_MAX) {
              pulses.push({ i, j, t: 0, speed: 0.02 + Math.random() * 0.025 })
              break
            }
          }
        }
      }
      draw()
      raf = requestAnimationFrame(step)
    }

    const onResize = () => { build(); if (reduced) draw() }
    const ro = new ResizeObserver(onResize)
    ro.observe(parent)
    build()
    if (reduced) draw()  // 减少动效偏好：静态一帧
    else raf = requestAnimationFrame(step)

    // 主题切换：暗色循环每帧自读；静态模式下重绘一帧
    const mo = new MutationObserver(() => { if (reduced) draw() })
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      mo.disconnect()
    }
  }, [])

  return <canvas ref={canvasRef} aria-hidden="true" />
}
