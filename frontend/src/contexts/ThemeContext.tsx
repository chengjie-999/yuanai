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

function getLocalTheme(): Theme | null {
  const saved = localStorage.getItem(STORAGE_KEY)
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
    const token = localStorage.getItem('token')
    if (!token) return
    fetchTheme().then((serverTheme) => {
      if (serverTheme === 'light' || serverTheme === 'dark') {
        setTheme(serverTheme)
        localStorage.setItem(STORAGE_KEY, serverTheme)
      }
    })
  }, [])

  // Apply theme to DOM
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'light' ? 'dark' : 'light'
      const token = localStorage.getItem('token')
      if (token) saveThemeToServer(next)
      return next
    })
  }, [])

  const set = useCallback((t: Theme) => {
    setTheme(t)
    const token = localStorage.getItem('token')
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
