import { useEffect, useRef, useState } from 'react'

/* ============================================================
   小元数据冲刺 — 首页轻量跑酷小游戏（Canvas 零依赖）
   主题对应项目：小元在数据世界奔跑，跳过「脏数据/异常值」，
   收集「数据点」得分。玩法同浏览器断网恐龙游戏：
   空格/点击/触摸起跳；先播放自动演示（attract 模式），点击进入游戏。
   ============================================================ */

type GameState = 'attract' | 'ready' | 'playing' | 'over'

interface Obstacle { x: number; w: number; h: number; kind: 'dirty' | 'outlier' | 'gap' }
interface Dot { x: number; y: number; taken: boolean }

const GRAVITY = 0.9
const JUMP_V = 13.5
const BASE_SPEED = 5
const GROUND_H = 92  // 地面高度（距画布底部）
const BALL_R = 15    // 角色滚动球半径

export default function DataRunGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [state, setState] = useState<GameState>('attract')
  const [best, setBest] = useState(() => Number(localStorage.getItem('yuanai-run-high') || 0))
  const stateRef = useRef<GameState>('attract')
  stateRef.current = state
  const scoreRef = useRef(0)
  // best 变化不重启游戏循环，走 ref 读取
  const bestRef = useRef(best)
  useEffect(() => { bestRef.current = best }, [best])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = canvas.width
    const H = canvas.height
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    // Hero 恒为深蓝渐变底：固定深色调色板 + 半透明画布，与页面浑然一体
    const C = {
      bg: 'rgba(13,26,48,0.45)',
      ground: 'rgba(26,42,68,0.75)',
      line: 'rgba(120,160,210,0.35)',
      char: '#4da6ff',
      charDark: '#6fb1ff',
      dirty: '#ef5350',
      outlier: '#ffa726',
      dot: '#66d36e',
      text: 'rgba(210,225,250,0.9)',
    }

    // 游戏世界状态
    const world = {
      vy: 0, y: GROUND_H, onGround: true,
      obstacles: [] as Obstacle[],
      dots: [] as Dot[],
      speed: BASE_SPEED,
      spawnTimer: 0,
      dead: false,
    }

    const resetWorld = () => {
      world.vy = 0; world.y = GROUND_H; world.onGround = true
      world.obstacles = []; world.dots = []
      world.speed = BASE_SPEED; world.spawnTimer = 0; world.dead = false
      scoreRef.current = 0
    }

    const spawnObstacle = () => {
      const roll = Math.random()
      let kind: Obstacle['kind'] = 'dirty'
      if (roll < 0.32) kind = 'gap'
      else if (roll < 0.62) kind = 'outlier'
      if (kind === 'gap') {
        world.obstacles.push({ x: W + 20, w: 26, h: 4, kind })
      } else if (kind === 'outlier') {
        world.obstacles.push({ x: W + 20, w: 18, h: 34, kind })
      } else {
        world.obstacles.push({ x: W + 20, w: 22, h: 30, kind })
      }
    }

    const spawnDot = () => {
      const y = GROUND_H + 45 + Math.random() * 55
      world.dots.push({ x: W + 40, y, taken: false })
    }

    const jump = () => {
      if (world.onGround) { world.vy = JUMP_V; world.onGround = false }
    }

    // ---- 输入 ----
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space' || e.code === 'ArrowUp') {
        e.preventDefault()
        if (stateRef.current === 'attract') { startGame() }
        else if (stateRef.current === 'ready') { startGame() }
        else if (stateRef.current === 'playing') jump()
        else if (stateRef.current === 'over') { resetWorld(); setState('ready') }
      }
    }
    const onPointer = () => {
      if (stateRef.current === 'attract' || stateRef.current === 'ready') startGame()
      else if (stateRef.current === 'playing') jump()
      else if (stateRef.current === 'over') { resetWorld(); setState('ready') }
    }
    window.addEventListener('keydown', onKey)
    canvas.addEventListener('pointerdown', onPointer)

    const startGame = () => {
      resetWorld()
      setState('playing')
      jump()
    }

    // ---- 主循环 ----
    let raf = 0
    let last = performance.now()
    let attractJumpT = 0
    let dist = 0

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      const dt = Math.min((now - last) / 16.7, 2.2)  // 每帧归一化（60fps 基准）
      last = now
      const st = stateRef.current

      // 物理与推进
      if (st === 'playing' || st === 'attract') {
        if (st === 'playing') world.speed = BASE_SPEED + Math.min(scoreRef.current * 0.06, 4.5)
        dist += world.speed * dt
        if (st === 'playing') {
          scoreRef.current = Math.floor(dist / 14)
        }
        world.vy -= GRAVITY * dt
        world.y += world.vy * dt
        if (world.y <= GROUND_H) { world.y = GROUND_H; world.vy = 0; world.onGround = true }

        // attract：自动跳（演示）
        if (st === 'attract') {
          attractJumpT -= dt
          if (attractJumpT <= 0 && world.onGround) { jump(); attractJumpT = 55 + Math.random() * 50 }
        }

        // 障碍推进 + 生成
        for (const o of world.obstacles) o.x -= world.speed * dt
        for (const d of world.dots) d.x -= world.speed * dt
        world.obstacles = world.obstacles.filter((o) => o.x > -60)
        world.dots = world.dots.filter((d) => d.x > -20 && !d.taken)
        world.spawnTimer -= dt
        if (world.spawnTimer <= 0) {
          world.spawnTimer = 70 + Math.random() * 55
          if (Math.random() < 0.55) spawnObstacle()
          if (Math.random() < 0.4) spawnDot()
        }

        // 碰撞（球 AABB）
        const cx = 64, cw = BALL_R * 2, ch = BALL_R * 2
        const cy = H - world.y - BALL_R * 2
        for (const o of world.obstacles) {
          if (o.kind === 'gap') {
            // 空值坑：落地踩坑即失败
            if (world.onGround && world.y <= GROUND_H + 1 &&
              o.x < cx + cw - 4 && o.x + o.w > cx + 4) {
              if (st === 'playing') gameOver()
            }
          } else if (o.x < cx + cw && o.x + o.w > cx) {
            const oy = H - GROUND_H - o.h
            if (cy + ch > oy && cy < oy + o.h + 2) {
              if (st === 'playing') gameOver()
              else { /* attract 撞上就重来演示 */ resetWorld() }
            }
          }
        }
        for (const d of world.dots) {
          if (!d.taken && Math.abs(d.x - cx) < 30 && Math.abs(d.y - (cy + BALL_R)) < 42) {
            d.taken = true
            if (st === 'playing') { scoreRef.current += 15 }
          }
        }
      }

      // ---- 渲染 ----
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, W, H)
      // 画布全透明：Hero 深蓝渐变直接透出，游戏与页面背景相融

      // 远景数据流（飘动的 0/1，散布于加高后的整幅画布）
      ctx.fillStyle = 'rgba(140,170,220,0.16)'
      for (let i = 0; i < 14; i++) {
        const fx = (W - ((dist * 0.5 + i * 97) % (W + 40))) + 20
        const fy = 30 + ((i * 83) % (H - GROUND_H - 40))
        ctx.font = '11px monospace'
        ctx.fillText(i % 2 ? '1' : '0', fx, fy)
      }

      // 地面
      ctx.fillStyle = C.ground
      ctx.fillRect(0, H - GROUND_H + 6, W, GROUND_H - 6)
      ctx.strokeStyle = C.line
      ctx.beginPath()
      ctx.moveTo(0, H - GROUND_H + 6.5)
      ctx.lineTo(W, H - GROUND_H + 6.5)
      ctx.stroke()
      // 地面刻度（数据网格感）
      ctx.fillStyle = C.line
      for (let i = 0; i < 10; i++) {
        const gx = (W - ((dist * 1 + i * 89) % (W + 30))) + 10
        ctx.fillRect(gx, H - 16, 2, 10)
      }

      // 数据点（收集物）
      for (const d of world.dots) {
        if (d.taken) continue
        const dy = H - d.y
        ctx.fillStyle = C.dot
        ctx.beginPath()
        ctx.arc(d.x, dy, 5, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = 'rgba(255,255,255,0.75)'
        ctx.font = '7px monospace'
        ctx.fillText('D', d.x - 2.4, dy + 2.4)
      }

      // 障碍
      for (const o of world.obstacles) {
        const oy = H - GROUND_H
        if (o.kind === 'dirty') {
          ctx.fillStyle = C.dirty
          ctx.fillRect(o.x, oy - o.h, o.w, o.h)
          ctx.strokeStyle = 'rgba(255,255,255,0.5)'
          ctx.strokeRect(o.x, oy - o.h, o.w, o.h)
          ctx.beginPath()
          ctx.moveTo(o.x + 4, oy - o.h + 4); ctx.lineTo(o.x + o.w - 4, oy - 4)
          ctx.moveTo(o.x + o.w - 4, oy - o.h + 4); ctx.lineTo(o.x + 4, oy - 4)
          ctx.stroke()
        } else if (o.kind === 'outlier') {
          ctx.fillStyle = C.outlier
          ctx.beginPath()
          ctx.moveTo(o.x, oy)
          ctx.lineTo(o.x + o.w / 2, oy - o.h)
          ctx.lineTo(o.x + o.w, oy)
          ctx.closePath()
          ctx.fill()
        } else {
          ctx.fillStyle = C.dirty
          ctx.fillRect(o.x, oy - o.h, o.w, o.h)
        }
      }

      // 小元角色：滚动球（白色标记点随滚动旋转）
      const bx = 64
      const by = H - world.y - BALL_R
      const rollAngle = dist / BALL_R
      ctx.fillStyle = C.charDark
      ctx.beginPath()
      ctx.arc(bx, by, BALL_R, 0, Math.PI * 2)
      ctx.fill()
      // 高光
      ctx.fillStyle = 'rgba(255,255,255,0.28)'
      ctx.beginPath()
      ctx.arc(bx - 4, by - 6, BALL_R - 8, 0, Math.PI * 2)
      ctx.fill()
      // 滚动标记点
      ctx.fillStyle = 'rgba(255,255,255,0.9)'
      ctx.beginPath()
      ctx.arc(bx + Math.cos(rollAngle) * (BALL_R - 5), by + Math.sin(rollAngle) * (BALL_R - 5), 4, 0, Math.PI * 2)
      ctx.fill()

      // 分数（右上角，极简）
      if (st === 'playing' || st === 'over') {
        ctx.fillStyle = C.text
        ctx.font = 'bold 13px system-ui'
        ctx.textAlign = 'right'
        ctx.fillText(`数据点 ${scoreRef.current}`, W - 12, 22)
        ctx.textAlign = 'left'
      }
    }

    const gameOver = () => {
      world.dead = true
      setState('over')
      const newBest = Math.max(bestRef.current, scoreRef.current)
      if (newBest > bestRef.current) { setBest(newBest); bestRef.current = newBest; localStorage.setItem('yuanai-run-high', String(newBest)) }
    }

    resetWorld()
    raf = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('keydown', onKey)
      canvas.removeEventListener('pointerdown', onPointer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <canvas
      ref={canvasRef}
      width={760}
      height={280}
      style={{
        width: '100%', height: 'auto', borderRadius: 12,
        background: 'transparent', cursor: 'pointer',
        touchAction: 'manipulation', display: 'block',
      }}
      aria-label="小元数据冲刺小游戏"
    />
  )
}
