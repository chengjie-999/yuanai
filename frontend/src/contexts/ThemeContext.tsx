import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { fetchTheme, saveTheme as saveThemeToServer } from '../api'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  isDark: boolean
  toggle: () => void
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeState>({
  theme: 'light', isDark: false, toggle: () => {}, setTheme: () => {},
})

const STORAGE_KEY = 'theme'

/* 存储受限环境（隐私模式/被禁 storage）裸读 localStorage 抛 SecurityError——
   P5 收敛：全部读写包安全壳（2026-10-24） */
function safeGet(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function safeSet(key: string, value: string): void {
  try { localStorage.setItem(key, value) } catch { /* 主题不落盘仅本次生效 */ }
}

function getLocalTheme(): Theme | null {
  const saved = safeGet(STORAGE_KEY)
  if (saved === 'dark' || saved === 'light') return saved
  return null
}

function getSystemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => getLocalTheme() || getSystemTheme())

  // On mount, if user is logged in, fetch server theme (overrides local)
  useEffect(() => {
    const token = safeGet('token')
    if (!token) return
    fetchTheme().then((serverTheme) => {
      if (serverTheme === 'light' || serverTheme === 'dark') {
        setTheme(serverTheme)
        safeSet(STORAGE_KEY, serverTheme)
      }
    })
  }, [])

  // Apply theme to DOM
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    safeSet(STORAGE_KEY, theme)
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'light' ? 'dark' : 'light'
      const token = safeGet('token')
      if (token) saveThemeToServer(next)
      return next
    })
  }, [])

  const set = useCallback((t: Theme) => {
    setTheme(t)
    const token = safeGet('token')
    if (token) saveThemeToServer(t)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, isDark: theme === 'dark', toggle, setTheme: set }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
