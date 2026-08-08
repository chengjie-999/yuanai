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
          {/* Stars */}
          <circle cx="15" cy="20" r="1" fill="#90a4ae" opacity="0.35">
            <animate attributeName="opacity" values="0.35;0.1;0.35" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="85" cy="16" r="1.2" fill="#90a4ae" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.55;0.3" dur="2.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="8" cy="62" r="0.8" fill="#90a4ae" opacity="0.25">
            <animate attributeName="opacity" values="0.25;0.5;0.25" dur="3.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="92" cy="72" r="1" fill="#90a4ae" opacity="0.3">
            <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2.8s" repeatCount="indefinite" />
          </circle>
          {/* Outer glow */}
          <circle cx="50" cy="50" r="45" fill="#b39ddb" opacity="0.04" />
          {/* Headphones — band */}
          <path d="M22 40 Q22 12 50 10 Q78 12 78 40" fill="none" stroke="#546e7a" strokeWidth="5" strokeLinecap="round" />
          {/* Headphones — ear cups */}
          <rect x="14" y="36" rx="4" ry="4" width="12" height="22" fill="#3d4a52" />
          <rect x="74" y="36" rx="4" ry="4" width="12" height="22" fill="#3d4a52" />
          <rect x="16" y="38" rx="2" ry="2" width="8" height="18" fill="#4d5a62" />
          <rect x="76" y="38" rx="2" ry="2" width="8" height="18" fill="#4d5a62" />
          {/* Head */}
          <circle cx="50" cy="52" r="32" fill="#3d4a52" />
          <circle cx="50" cy="52" r="27" fill="#4d5a62" />
          {/* Orbiting dots */}
          {[[14,32],[86,32],[22,74],[78,74]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?28:36} y1={i<2?42:60} x2={x} y2={y} stroke="#5a6a74" strokeWidth="3" strokeLinecap="round" />
              <circle cx={x} cy={y} r="4.5" fill="#90a4ae">
                <animate attributeName="opacity" values="0.35;0.6;0.35" dur={`${2.5+i*0.4}s`} repeatCount="indefinite" />
              </circle>
            </g>
          ))}
          {/* Sleep mask */}
          <path d="M22 44 Q50 38 78 44 Q79 50 50 48 Q21 50 22 44Z" fill="#382844" />
          <path d="M22 44 Q50 38 78 44" fill="none" stroke="#4a3858" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M22 47 Q50 50 78 47" fill="none" stroke="#2a1c34" strokeWidth="0.8" opacity="0.5" />
          <path d="M22 45 L14 41" stroke="#4a3858" strokeWidth="2" strokeLinecap="round" opacity="0.7" />
          <path d="M78 45 L86 41" stroke="#4a3858" strokeWidth="2" strokeLinecap="round" opacity="0.7" />
          {/* Smile */}
          <path d="M43 64 Q50 69 57 64" fill="none" stroke="#90a4ae" strokeWidth="1.8" strokeLinecap="round" opacity="0.5" />
          {/* Blush */}
          <ellipse cx="28" cy="55" rx="5" ry="4" fill="#f48fb1" opacity="0.16" />
          <ellipse cx="72" cy="55" rx="5" ry="4" fill="#f48fb1" opacity="0.16" />
          {/* Zzz */}
          <g opacity="0">
            <animate attributeName="opacity" values="0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
            <animateTransform attributeName="transform" type="translate" values="4,4;4,-2;4,-8;4,-8;4,-2" dur="4s" repeatCount="indefinite" />
            <text x="62" y="26" fill="#4db6ac" fontSize="12" fontWeight="bold" fontFamily="sans-serif">z</text>
          </g>
          <g opacity="0">
            <animate attributeName="opacity" values="0;0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
            <animateTransform attributeName="transform" type="translate" values="8,8;8,2;8,-2;8,-8;8,-8;8,-2" dur="4s" repeatCount="indefinite" />
            <text x="68" y="20" fill="#4db6ac" fontSize="16" fontWeight="bold" fontFamily="sans-serif">Z</text>
          </g>
          <g opacity="0">
            <animate attributeName="opacity" values="0;0;0;0;0.7;0.7;0" dur="4s" repeatCount="indefinite" />
            <animateTransform attributeName="transform" type="translate" values="12,12;12,6;12,2;12,-2;12,-8;12,-8;12,-2" dur="4s" repeatCount="indefinite" />
            <text x="76" y="14" fill="#4db6ac" fontSize="20" fontWeight="bold" fontFamily="sans-serif">Z</text>
          </g>
        </svg>
      ) : (
        <svg viewBox="0 0 100 100" width={size} height={size}>
          <circle cx="50" cy="50" r="42" fill="#42a5f5" opacity="0.08" />
          <circle cx="50" cy="52" r="32" fill="#1976d2" />
          <circle cx="50" cy="52" r="27" fill="#42a5f5" />
          {[[12,30],[88,30],[20,76],[80,76]].map(([x,y],i)=>(
            <g key={i}>
              <line x1={i<2?26:34} y1={i<2?40:62} x2={x} y2={y} stroke="#1976d2" strokeWidth="5" strokeLinecap="round" />
              <circle cx={x} cy={y} r="6" fill="#90caf9" />
            </g>
          ))}
          <ellipse cx="38" cy="44" rx="7" ry="8" fill="#fff" />
          <ellipse cx="38" cy="44" rx="4" ry="5" fill="#311b92" />
          <circle cx="40" cy="42" r="2" fill="#fff" opacity="0.9" />
          <path d="M53 44 Q59 38 65 44" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0">
            <animate attributeName="opacity" values="0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1;1;0" dur="4s" repeatCount="indefinite" />
          </path>
          <ellipse cx="59" cy="44" rx="7" ry="8" fill="#fff">
            <animate attributeName="ry" values="8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;8;3;1;8" dur="4s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="59" cy="44" rx="4" ry="5" fill="#0d47a1">
            <animate attributeName="ry" values="5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;5;1.5;0.5;5" dur="4s" repeatCount="indefinite" />
          </ellipse>
          <circle cx="61" cy="42" r="2" fill="#fff" opacity="0.9">
            <animate attributeName="opacity" values="0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0.9;0;0;0.9" dur="4s" repeatCount="indefinite" />
          </circle>
          <path d="M42 60 Q50 70 58 60" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity="0.85" />
          <ellipse cx="30" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
          <ellipse cx="70" cy="55" rx="6" ry="4" fill="#f8bbd0" opacity="0.4" />
        </svg>
      )}

      {/* 对话气泡 */}
      {bubble && (
        <div style={{
          position: 'absolute', bottom: '100%', left: '50%',
          transform: 'translateX(-50%)',
          marginBottom: 10,
          background: isDark ? '#3c3f41' : '#ffffff',
          border: `1px solid ${isDark ? '#45494a' : '#d0d7de'}`,
          borderRadius: 12,
          padding: '12px 16px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          whiteSpace: 'nowrap',
          zIndex: 100,
          animation: 'bubble-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
          {/* 三角箭头 */}
          <div style={{
            position: 'absolute', top: '100%', left: '50%',
            transform: 'translateX(-50%)',
            width: 0, height: 0,
            borderLeft: '7px solid transparent',
            borderRight: '7px solid transparent',
            borderTop: `7px solid ${isDark ? '#3c3f41' : '#ffffff'}`,
            filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.1))',
          }} />
          <p style={{
            margin: '0 0 10px', fontSize: 14, fontWeight: 500,
            color: 'var(--text-primary)',
          }}>
            {isDark ? '☀️ 切换到亮色模式？' : '🌙 切换到暗色模式？'}
          </p>
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
          from { opacity: 0; transform: translateX(-50%) translateY(6px) scale(0.92); }
          to   { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}
