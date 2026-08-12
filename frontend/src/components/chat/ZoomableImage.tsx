import { useState, useRef, useCallback, useEffect } from 'react'

interface Props {
  src: string
  onClose: () => void
}

export default function ZoomableImage({ src, onClose }: Props) {
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const lastPos = useRef({ x: 0, y: 0 })
  const lastPinchDist = useRef(0)
  const lastPinchScale = useRef(1)
  const containerRef = useRef<HTMLDivElement>(null)

  const clampScale = (s: number) => Math.max(0.3, Math.min(s, 10))

  // 鼠标滚轮缩放
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

  // 鼠标拖拽平移
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return  // 缩放到 ≤1 时不拖拽，点击关闭
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

  // 点击背景关闭（未缩放时点击图片也关闭）
  const onBackdropClick = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) onClose()
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

  // 双击切换缩放
  const onDoubleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (scale > 1.1) {
      setScale(1)
      setOffset({ x: 0, y: 0 })
    } else {
      setScale(2.5)
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
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
        zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center',
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

      {/* 缩放比例提示 */}
      {scale !== 1 && (
        <div style={{
          position: 'absolute', top: 20, left: 20, zIndex: 10,
          background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: 12,
          padding: '4px 10px', borderRadius: 12,
        }}>
          {Math.round(scale * 100)}%
        </div>
      )}

      {/* 重置按钮 */}
      {scale !== 1 && (
        <button
          onClick={(e) => { e.stopPropagation(); setScale(1); setOffset({ x: 0, y: 0 }) }}
          style={{
            position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 10,
            background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.25)',
            borderRadius: 8, padding: '6px 16px', fontSize: 13, cursor: 'pointer',
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.3)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.15)'}
        >重置缩放</button>
      )}

      <img
        src={src}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={onMouseDown}
        onDoubleClick={onDoubleClick}
        draggable={false}
        style={{
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          maxWidth: '90vw',
          maxHeight: '90vh',
          borderRadius: 8,
          boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
          cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in',
          transition: dragging ? 'none' : 'transform 0.15s ease',
          userSelect: 'none',
          pointerEvents: 'auto',
        }}
      />
    </div>
  )
}
