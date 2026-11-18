import { useEffect, useRef, useState } from 'react'
import type { ReactNode, CSSProperties } from 'react'
import { useIsMobile } from '../../hooks/useIsMobile'
import { isZoomViewerOpen } from './ZoomableImage'
import MobileSheetMenu from './MobileSheetMenu'

export interface BlockMenuItem {
  label: string
  onClick: () => void
  disabled?: boolean
}

/** 块级长按容器（T16 批次 2，2026-11-18）：HTML/SVG/Mermaid 块统一标
 *  `data-block-area` + 500ms 长按计时（滑动取消）+ 块级底部菜单。
 *
 * 互斥机制：
 * - 消息行级 onTouchStart 命中块内（closest('[data-block-area]')）即不启动
 *   行计时器——块长按弹块菜单，不再弹通用消息菜单
 * - 查看器打开（isZoomViewerOpen）时计时器直接跳过——放大后长按不生效
 * - 微信内（MicroMessenger）不弹自定义块菜单——原生菜单单独出现不叠加
 *   （适配而非对抗）；块下载功能经消息长按菜单兜底可达
 * - 松手补发的 click 落在菜单遮罩上，由菜单遮罩 onClick 吞掉（复用
 *   MobileSheetMenu 的即开即关保护），块自身的点击放大不叠加触发
 */
export default function BlockLongPress({ menuItems, children, style, ariaLabel }: {
  menuItems: BlockMenuItem[]
  children: ReactNode
  style?: CSSProperties
  ariaLabel?: string
}) {
  const isMobile = useIsMobile()
  const [menuOpen, setMenuOpen] = useState(false)
  const timerRef = useRef<number | null>(null)
  // 菜单打开后吞掉一次遮罩点击（长按松手补发的 click）防「即开即关」
  const suppressBackdropClickRef = useRef(false)

  const clear = () => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }
  useEffect(() => () => clear(), [])

  const isWx = /MicroMessenger/i.test(navigator.userAgent)
  // 微信内不弹块级菜单（原生菜单单独出现）；非移动端无长按语义
  const active = isMobile && !isWx && menuItems.length > 0

  const closeMenu = () => {
    if (suppressBackdropClickRef.current) {
      suppressBackdropClickRef.current = false
      return
    }
    setMenuOpen(false)
  }

  return (
    <div data-block-area aria-label={ariaLabel} style={style}
      onTouchStart={active ? (e) => {
        if (isZoomViewerOpen()) return
        clear()
        timerRef.current = window.setTimeout(() => {
          suppressBackdropClickRef.current = true
          setMenuOpen(true)
          window.setTimeout(() => { suppressBackdropClickRef.current = false }, 700)
        }, 500)
        void e
      } : undefined}
      onTouchMove={active ? () => clear() : undefined}
      onTouchEnd={active ? () => clear() : undefined}
    >
      {children}
      {menuOpen && <MobileSheetMenu items={menuItems} onClose={closeMenu} />}
    </div>
  )
}
