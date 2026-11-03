import { useState, useRef, useCallback, useEffect } from 'react'

/* ============================================================
   统一缩放/平移交互（2026-11-03 用户拍板：图片与 HTML/SVG 查看器同款体验）

   ZoomViewport：滚轮缩放（光标为中心）/ 拖拽平移 / 双击切换 2.5x / 移动端
   双指捏合 / Esc 关闭 / 比例提示 + 重置按钮。children 放在 transform 容器内，
   宿主只需提供尺寸确定的区域（flex:1 + minHeight:0 或固定宽高）。
   ZoomableImage（图片）与 MessageBubble 的 HtmlViewer（HTML/SVG）共用。
   ============================================================ */

export function ZoomViewport({ children, onClose, initialScale }: {
  children: React.ReactNode; onClose: () => void
  initialScale?: number  // 初始适配缩放（SVG 直渲：挂载测量固有尺寸后传入，≤1）
}) {
  const baseRef = useRef(1)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const lastPos = useRef({ x: 0, y: 0 })
  const lastPinchDist = useRef(0)
  const lastPinchScale = useRef(1)
  const containerRef = useRef<HTMLDivElement>(null)

  const clampScale = (s: number) => Math.max(0.3, Math.min(s, 10))
  const atBase = () => Math.abs(scale - baseRef.current) < 0.01

  // 初始适配（SVG 测量结果异步到达）：重置到适配缩放
  useEffect(() => {
    if (initialScale && initialScale > 0 && initialScale <= 1) {
      baseRef.current = initialScale
      setScale(initialScale)
      setOffset({ x: 0, y: 0 })
    }
  }, [initialScale])

  // 鼠标滚轮缩放（以光标位置为中心）
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.stopPropagation()
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left - rect.width / 2
    const my = e.clientY - rect.top - rect.height / 2
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
    setScale((prev) => {
      const next = clampScale(prev * factor)
      setOffset((off) => ({
        x: (off.x - mx) * (next / prev) + mx,
        y: (off.y - my) * (next / prev) + my,
      }))
      return next
    })
  }, [])

  // 鼠标拖拽平移（放大超过初始适配时）
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (atBase()) return
    e.stopPropagation()
    setDragging(true)
    lastPos.current = { x: e.clientX - offset.x, y: e.clientY - offset.y }
  }, [scale, offset])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging) return
    setOffset({ x: e.clientX - lastPos.current.x, y: e.clientY - lastPos.current.y })
  }, [dragging])

  const onMouseUp = useCallback(() => {
    setDragging(false)
  }, [])

  // 点击空白关闭（处于初始适配、未放大时）
  const onBackdropClick = useCallback((_e: React.MouseEvent) => {
    if (atBase()) onClose()
  }, [scale, onClose])

  // 移动端触摸缩放
  const getTouchDist = (touches: React.TouchList) => {
    const dx = touches[0].clientX - touches[1].clientX
    const dy = touches[0].clientY - touches[1].clientY
    return Math.hypot(dx, dy)
  }

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      e.stopPropagation()
      lastPinchDist.current = getTouchDist(e.touches)
      lastPinchScale.current = scale
    } else if (e.touches.length === 1 && scale > 1) {
      lastPos.current = { x: e.touches[0].clientX - offset.x, y: e.touches[0].clientY - offset.y }
      setDragging(true)
    }
  }, [scale, offset])

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      e.stopPropagation()
      const dist = getTouchDist(e.touches)
      if (lastPinchDist.current > 0) {
        const ratio = dist / lastPinchDist.current
        setScale(clampScale(lastPinchScale.current * ratio))
      }
    } else if (e.touches.length === 1 && dragging) {
      setOffset({ x: e.touches[0].clientX - lastPos.current.x, y: e.touches[0].clientY - lastPos.current.y })
    }
  }, [dragging])

  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    if (e.touches.length < 2) {
      lastPinchDist.current = 0
      setDragging(false)
    }
  }, [])

  // 双击切换缩放（回到初始适配 / 放大 2.5 倍）
  const onDoubleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (!atBase()) {
      setScale(baseRef.current)
      setOffset({ x: 0, y: 0 })
    } else {
      setScale(baseRef.current * 2.5)
    }
  }, [scale])

  // Esc 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      ref={containerRef}
      onClick={onBackdropClick}
      onWheel={onWheel}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      style={{
        // 占满宿主全屏（宿主 backdrop 用 column 布局 + flex:1 高度拉伸；
        // width 100% 补交叉轴）——容器若只有内容高度，放大后上下立即撞边
        // 被 overflow:hidden 裁剪（2026-11-03「上下区域限制」根因）
        position: 'relative', flex: 1, minHeight: 0, minWidth: 0, width: '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden', touchAction: 'none',
      }}
    >
      {/* 缩放比例提示（偏离初始适配时显示） */}
      {!atBase() && (
        <div style={{
          position: 'absolute', top: 12, left: 12, zIndex: 10,
          background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12,
          padding: '4px 10px', borderRadius: 12,
        }}>
          {Math.round(scale * 100)}%
        </div>
      )}

      {/* 重置按钮（回到初始适配） */}
      {!atBase() && (
        <button
          onClick={(e) => { e.stopPropagation(); setScale(baseRef.current); setOffset({ x: 0, y: 0 }) }}
          style={{
            position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 10,
            background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.25)',
            borderRadius: 8, padding: '6px 16px', fontSize: 13, cursor: 'pointer',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
        >重置缩放</button>
      )}

      {/* 内容（transform 缩放/平移） */}
      <div
        onClick={(e) => e.stopPropagation()}
        onMouseDown={onMouseDown}
        onDoubleClick={onDoubleClick}
        style={{
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          transition: dragging ? 'none' : 'transform 0.15s ease',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          maxWidth: '100%', maxHeight: '100%',
        }}
      >
        {children}
      </div>
    </div>
  )
}

interface Props {
  src: string
  onClose: () => void
}

export default function ZoomableImage({ src, onClose }: Props) {
  return (
    <div
      onClick={() => onClose()}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
        zIndex: 9999, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden', touchAction: 'none',
      }}
    >
      {/* 关闭按钮 */}
      <button
        onClick={(e) => { e.stopPropagation(); onClose() }}
        style={{
          position: 'absolute', top: 16, right: 16, zIndex: 10,
          width: 36, height: 36, borderRadius: '50%',
          border: 'none', background: 'rgba(255,255,255,0.15)',
          color: '#fff', fontSize: 18, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
      >✕</button>

      <ZoomViewport onClose={onClose}>
        <img
          src={src}
          draggable={false}
          style={{
            maxWidth: '90vw',
            maxHeight: '90vh',
            borderRadius: 8,
            boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
            cursor: 'grab',
            userSelect: 'none',
            pointerEvents: 'auto',
          }}
        />
      </ZoomViewport>
    </div>
  )
}
