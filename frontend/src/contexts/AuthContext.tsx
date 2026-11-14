import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { checkToken, getToken, getStoredUser, setStoredUser, setAuthFailedHandler } from '../api'

interface AuthState {
  token: string | null
  user: any
  loading: boolean
  login: (token: string, user: any, rememberMe?: boolean) => void
  logout: () => void
  refresh: () => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthState>({
  token: null, user: null, loading: true,
  login: () => {}, logout: () => {}, refresh: () => {}, isAdmin: false,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 2026-11-14 掉登录修复：本地优先——token 与缓存的用户信息同步恢复，
    // 登录态不依赖服务端校验的往返（此前挂载即发 /auth/check，任何一次
    // 网络抖动/后端重启/限流都判失效清 token，频繁刷新=反复抽检必掉登录）；
    // 服务端校验改后台软校验：明确 401/403 才登出，瞬时失败保持现状
    const saved = getToken()
    if (saved) {
      setToken(saved)
      const stored = getStoredUser()
      if (stored) setUser(stored)
      setLoading(false)  // 本地态即登录态：不等服务端校验（校验仅后台软刷新）
      checkToken().then((data) => {
        if (data.valid && data.user) {
          setUser(data.user)
          setStoredUser(data.user)  // 服务端用户信息更新本地缓存
        } else if (!data.transient) {
          // 明确鉴权拒绝（401/403）：清 token 提示重新登录
          if (data.detail) {
            try { sessionStorage.setItem('loginError', data.detail) } catch { /* 存储受限 */ }
          }
          try { localStorage.removeItem('token') } catch { /* 存储受限 */ }
          try { sessionStorage.removeItem('token') } catch { /* 存储受限 */ }
          setStoredUser(null)
          setToken(null)
          setUser(null)
        }
        // transient（网络/5xx/限流）：保持本地登录态，下次刷新再校验
      })
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback((newToken: string, newUser: any, rememberMe = true) => {
    if (!newToken) return
    // 存储受限环境写不进去仅本次会话有效（token 在内存中照常工作）
    if (rememberMe) {
      try { localStorage.setItem('token', newToken) } catch { /* 存储受限 */ }
      try { sessionStorage.removeItem('token') } catch { /* 存储受限 */ }
    } else {
      try { sessionStorage.setItem('token', newToken) } catch { /* 存储受限 */ }
      try { localStorage.removeItem('token') } catch { /* 存储受限 */ }
    }
    setStoredUser(newUser)
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    try { localStorage.removeItem('token') } catch { /* 存储受限 */ }
    try { sessionStorage.removeItem('token') } catch { /* 存储受限 */ }
    setStoredUser(null)
    setToken(null)
    setUser(null)
  }, [])

  const refresh = useCallback(() => {
    checkToken().then((data) => {
      if (data.valid && data.user) {
        setUser(data.user)
        setStoredUser(data.user)
      }
    })
  }, [])

  // 全局 401 自动登出（2026-10-30 #24）：改密吊销/登录被踢/冻结等——
  // 任何请求 401 → 清 token → 登录页显示原因（LoginPage 读 loginError）
  useEffect(() => {
    setAuthFailedHandler((detail: string) => {
      try { sessionStorage.setItem('loginError', detail) } catch { /* 忽略 */ }
      logout()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    })
    return () => setAuthFailedHandler(null)
  }, [logout])

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout, refresh, isAdmin: user?.role === 'admin' }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
