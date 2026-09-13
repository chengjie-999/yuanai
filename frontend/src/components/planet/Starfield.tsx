import { useEffect, useRef } from 'react'

/* 星空背景 — Canvas 粒子星野（知识星球页专属）
   零依赖：requestAnimationFrame 循环，闪烁 + 缓慢漂移；
   明暗主题自适应（暗色星亮、亮色星淡），页面隐藏时自动暂停省电。 */
export default function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let raf = 0
    let stars: { x: number; y: number; r: number; phase: number; speed: number; vy: number }[] = []

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      const count = Math.min(110, Math.floor((canvas.width * canvas.height) / 16000))
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.1 + 0.4,
        phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 0.9,
        vy: 0.02 + Math.random() * 0.05,
      }))
    }
    resize()
    window.addEventListener('resize', resize)

    const draw = () => {
      if (document.hidden) { raf = requestAnimationFrame(draw); return }  // 后台省电
      const dark = document.documentElement.getAttribute('data-theme') === 'dark'
      const baseAlpha = dark ? 0.75 : 0.5
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const now = performance.now() / 1000
      for (const s of stars) {
        s.y += s.vy
        if (s.y > canvas.height + 2) { s.y = -2; s.x = Math.random() * canvas.width }
        const tw = 0.55 + 0.45 * Math.sin(now * s.speed + s.phase)
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = dark
          ? `rgba(255,255,255,${(baseAlpha * tw).toFixed(3)})`
          : `rgba(31,35,40,${(baseAlpha * tw * 0.6).toFixed(3)})`
        ctx.fill()
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas ref={canvasRef}
      style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} />
  )
}
