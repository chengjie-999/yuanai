import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { checkToken, setStoredUser } from '../api'

interface AuthState {
  token: string | null
  user: any
  loading: boolean
  login: (token: string, user: any, rememberMe?: boolean) => void
  logout: () => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthState>({
  token: null, user: null, loading: true,
  login: () => {}, logout: () => {}, isAdmin: false,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const saved = localStorage.getItem('token') || sessionStorage.getItem('token')
    if (saved) {
      checkToken().then((data) => {
        if (data.valid && data.user) {
          setToken(saved)
          setUser(data.user)
        } else {
          if (data.detail) sessionStorage.setItem('loginError', data.detail)
          localStorage.removeItem('token')
          sessionStorage.removeItem('token')
        }
        setLoading(false)
      })
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback((newToken: string, newUser: any, rememberMe = true) => {
    if (!newToken) return
    if (rememberMe) {
      localStorage.setItem('token', newToken)
      sessionStorage.removeItem('token')
    } else {
      sessionStorage.setItem('token', newToken)
      localStorage.removeItem('token')
    }
    setStoredUser(newUser)
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    sessionStorage.removeItem('token')
    setStoredUser(null)
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
