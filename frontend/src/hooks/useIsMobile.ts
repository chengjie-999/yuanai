import { useState, useEffect } from 'react'

/* 移动端判定（P5 响应式共享 hook）：≤768px 视为移动布局；
   resize 监听实时切换（ChatPage 同款模式抽为共用） */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth <= 768)
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return isMobile
}
