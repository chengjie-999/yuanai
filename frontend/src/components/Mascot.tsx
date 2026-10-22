import { useState, useRef, useEffect } from 'react'
import { useTheme } from '../contexts/ThemeContext'

/** 小元AI 吉祥物 — 欢迎页和登录页共享，点击切换暗色/亮色模式 */
export default function Mascot({ size = 80 }: { size?: number }) {
  const { isDark, toggle } = useTheme()
  const [bubble, setBubble] = useState(false)
  const [switching, setSwitching] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // 点击外部关闭气泡
  useEffect(() => {
    if (!bubble) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setBubble(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [bubble])

  const handleToggle = () => {
    setSwitching(true)
    toggle()
    setTimeout(() => {
      setSwitching(false)
      setBubble(false)
    }, 400)
  }

  return (
    <div
      ref={ref}
      onClick={() => { if (!bubble) setBubble(true) }}
      style={{
        position: 'relative', width: size, height: size,
        cursor: 'pointer',
        animation: isDark ? 'float 5s ease-in-out infinite' : 'float 3s ease-in-out infinite',
        transition: 'transform 0.2s',
        transform: switching ? 'scale(1.15)' : bubble ? 'scale(1.08)' : 'scale(1)',
        userSelect: 'none',
        WebkitTapHighlightColor: 'transparent',
      }}
      title={`点击切换到${isDark ? '亮色' : '暗色'}模式`}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setBubble(true) } }}
      aria-label={`切换主题，当前为${isDark ? '暗色' : '亮色'}模式`}
    >
      {isDark ? (
        <svg viewBox="0 0 100 100" width={size} height={size}>
          <defs>
            <linearGradient id="mascot-grad-d" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#93c5fd" />
              <stop offset="100%" stopColor="#3b82f6" />
            </linearGradient>
          </defs>
          {/* Stars（同色系装饰点） */}
          <circle cx="15" cy="20" r="1" fill="#93c5fd" opacity="0.35">
            <animate attributeName="opacity" values="0.35;0.1;0.35" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="85" cy="16" r="1.2" fill="#93c5fd" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.55;0.3" dur="2.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="8" cy="62" r="0.8" fill="#93c5fd" opacity="0.25">
            <animate attributeName="opacity" values="0.25;0.5;0.25" dur="3.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="92" cy="72" r="1" fill="#93c5fd" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2.8s" repeatCount="indefinite" />
          </circle>
          {/* 光晕底座 */}
          <circle cx="50" cy="50" r="44" fill="url(#mascot-grad-d)" opacity="0.12" />
          {/* 主体 — 单一渐变球（无拟人五官） */}
          <circle cx="50" cy="52" r="32" fill="url(#mascot-grad-d)" />
          <circle cx="50" cy="52" r="32" fill="none" stroke="#ffffff" strokeOpacity="0.15" strokeWidth="1.5" />
          {/* 中央核心 — 「元」字标识（品牌识别元素，favicon 尺寸也可辨认） */}
          <text x="50" y="54" textAnchor="middle" dominantBaseline="central"
            fontSize="32" fontWeight="700" fill="#ffffff" opacity="0.96"
            fontFamily="system-ui, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif">
            元
          </text>
          {/* 环绕轨道点 */}
          {[[14,32],[86,32],[22,74],[78,74]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?28:36} y1={i<2?42:60} x2={x} y2={y} stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
              <circle cx={x} cy={y} r="4.5" fill="#bfdbfe">
                <animate attributeName="opacity" values="0.45;0.85;0.45" dur={`${2.5+i*0.4}s`} repeatCount="indefinite" />
              </circle>
            </g>
          ))}
        </svg>
      ) : (
        <svg viewBox="0 0 100 100" width={size} height={size}>
          <defs>
            <linearGradient id="mascot-grad-l" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#60a5fa" />
              <stop offset="100%" stopColor="#1d4ed8" />
            </linearGradient>
          </defs>
          {/* 光晕底座 */}
          <circle cx="50" cy="50" r="44" fill="url(#mascot-grad-l)" opacity="0.10" />
          {/* 主体 — 单一渐变球（无拟人五官） */}
          <circle cx="50" cy="52" r="32" fill="url(#mascot-grad-l)" />
          <circle cx="50" cy="52" r="32" fill="none" stroke="#ffffff" strokeOpacity="0.18" strokeWidth="1.5" />
          {/* 中央核心 — 「元」字标识（品牌识别元素，favicon 尺寸也可辨认） */}
          <text x="50" y="54" textAnchor="middle" dominantBaseline="central"
            fontSize="32" fontWeight="700" fill="#ffffff" opacity="0.96"
            fontFamily="system-ui, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif">
            元
          </text>
          {/* 环绕轨道点 */}
          {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" />
              <circle cx={x} cy={y} r="5" fill="#93c5fd">
                <animate attributeName="opacity" values="0.45;0.85;0.45" dur={`${2.5+i*0.4}s`} repeatCount="indefinite" />
              </circle>
            </g>
          ))}
        </svg>
      )}

      {/* 对话气泡 — 显示在右侧 */}
      {bubble && (
        <div style={{
          position: 'absolute', top: '50%', left: '100%',
          transform: 'translateY(-50%)',
          marginLeft: 12,
          background: isDark ? 'var(--bg-tertiary)' : '#ffffff',
          border: `1px solid var(--border)`,
          borderRadius: 12,
          padding: '12px 16px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          whiteSpace: 'nowrap',
          zIndex: 100,
          animation: 'bubble-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
          {/* 三角箭头 — 指向左侧吉祥物 */}
          <div style={{
            position: 'absolute', top: '50%', right: '100%',
            transform: 'translateY(-50%)',
            width: 0, height: 0,
            borderTop: '7px solid transparent',
            borderBottom: '7px solid transparent',
            borderRight: `7px solid ${isDark ? 'var(--bg-tertiary)' : '#ffffff'}`,
            filter: 'drop-shadow(-1px 0 1px rgba(0,0,0,0.08))',
          }} />
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            marginBottom: 10,
          }}>
            {isDark ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4da6ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
            <span style={{
              fontSize: 14, fontWeight: 500,
              color: 'var(--text-primary)',
            }}>
              {isDark ? '切换到亮色模式？' : '切换到暗色模式？'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            <button
              onClick={(e) => { e.stopPropagation(); handleToggle() }}
              style={{
                padding: '5px 16px', borderRadius: 6,
                border: 'none', background: 'var(--accent)', color: '#fff',
                fontSize: 13, fontWeight: 500, cursor: 'pointer',
              }}
            >
              切换
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setBubble(false) }}
              style={{
                padding: '5px 16px', borderRadius: 6,
                border: '1px solid var(--border)',
                background: 'transparent', color: 'var(--text-secondary)',
                fontSize: 13, cursor: 'pointer',
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 气泡动画 keyframe */}
      <style>{`
        @keyframes bubble-in {
          from { opacity: 0; transform: translateY(-50%) translateX(-6px) scale(0.92); }
          to   { opacity: 1; transform: translateY(-50%) translateX(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
