import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import apiClient, {
  API_BASE_URL,
  MOCK_MODE,
  setAccessToken as setApiAccessToken,
  setRefreshHandler as setApiRefreshHandler,
  setUnauthorizedHandler as setApiUnauthorizedHandler,
} from '../../lib/apiClient'
import useDashboardStore from '../dashboard/store/useDashboardStore'

const STORAGE_KEY = 'adinsights.auth'
const REFRESH_LEEWAY_MS = 60_000

interface LoginResponse {
  access: string
  refresh: string
  tenant_id: string
  user?: Record<string, unknown>
}

type AuthStatus = 'idle' | 'checking' | 'authenticating' | 'authenticated' | 'error'

type AuthContextValue = {
  status: AuthStatus
  isAuthenticated: boolean
  accessToken?: string
  tenantId?: string
  user?: Record<string, unknown>
  error?: string
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  statusMessage?: string
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

type StoredTokens = {
  access: string
  refresh: string
  tenantId: string
  user?: Record<string, unknown>
}

function decodeJwtExpiration(token: string): number | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) {
      return null
    }
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const decoded = atob(normalized)
    const parsed = JSON.parse(decoded) as { exp?: number }
    return typeof parsed.exp === 'number' ? parsed.exp : null
  } catch (error) {
    console.warn('Unable to decode JWT payload', error)
    return null
  }
}

function readStoredTokens(): StoredTokens | null {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as StoredTokens
    if (typeof parsed?.access === 'string' && typeof parsed?.refresh === 'string') {
      return parsed
    }
  } catch (error) {
    console.warn('Failed to parse stored auth state', error)
  }
  return null
}

function writeStoredTokens(tokens: StoredTokens | null): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return
  }
  if (tokens) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens))
  } else {
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

export function AuthProvider({ children }: PropsWithChildren): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>('idle')
  const [error, setError] = useState<string>()
  const [statusMessage, setStatusMessage] = useState<string>()
  const [accessToken, setAccessToken] = useState<string>()
  const [tenantId, setTenantId] = useState<string>()
  const [user, setUser] = useState<Record<string, unknown> | undefined>()
  const refreshTokenRef = useRef<string>()
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bootstrappedRef = useRef(false)

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current)
      refreshTimeoutRef.current = null
    }
  }, [])

  const logout = useCallback(() => {
    clearRefreshTimer()
    refreshTokenRef.current = undefined
    setAccessToken(undefined)
    setTenantId(undefined)
    setUser(undefined)
    setStatus('idle')
    setError(undefined)
    setStatusMessage(undefined)
    writeStoredTokens(null)
    useDashboardStore.getState().reset()
  }, [clearRefreshTimer])

  const applyTokens = useCallback((next: StoredTokens) => {
    setAccessToken(next.access)
    setTenantId(next.tenantId)
    setUser(next.user)
    refreshTokenRef.current = next.refresh
    writeStoredTokens(next)
  }, [])

  const refreshAccessToken = useCallback(async (): Promise<string | undefined> => {
    const refresh = refreshTokenRef.current
    if (!refresh) {
      logout()
      return undefined
    }

    if (MOCK_MODE && accessToken) {
      return accessToken
    }
    try {
      const response = await fetch(`${API_BASE_URL.replace(/\/$/, '')}/auth/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      })
      if (!response.ok) {
        throw new Error(`Refresh failed with status ${response.status}`)
      }
      const data = (await response.json()) as { access: string }
      const nextTokens: StoredTokens = {
        access: data.access,
        refresh,
        tenantId: tenantId ?? '',
        user,
      }
      applyTokens(nextTokens)
      setStatus('authenticated')
      setError(undefined)
      setStatusMessage(undefined)
      setApiAccessToken(data.access)
      return data.access
    } catch (refreshError) {
      console.error('Token refresh failed', refreshError)
      logout()
      return undefined
    }
  }, [accessToken, applyTokens, logout, tenantId, user])

  const login = useCallback(
    async (email: string, password: string) => {
      setStatus('authenticating')
      setError(undefined)
      setStatusMessage(undefined)
      try {
        let tokens: StoredTokens

        if (MOCK_MODE) {
          tokens = {
            access: `mock-access-${Date.now()}`,
            refresh: `mock-refresh-${Date.now()}`,
            tenantId: 'demo',
            user: { email },
          }
        } else {
          const response = await fetch(`${API_BASE_URL.replace(/\/$/, '')}/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          })
          if (!response.ok) {
            const detail = await response.text()
            throw new Error(detail || 'Invalid credentials')
          }
          const data = (await response.json()) as LoginResponse
          tokens = {
            access: data.access,
            refresh: data.refresh,
            tenantId: data.tenant_id,
            user: data.user,
          }
        }
        applyTokens(tokens)
        setStatus('authenticated')
        setError(undefined)
        setStatusMessage(undefined)
      } catch (loginError) {
        console.error('Login failed', loginError)
        const message = loginError instanceof Error ? loginError.message : 'Unable to login.'
        logout()
        setStatus('error')
        setError(message)
        setStatusMessage(undefined)
        throw loginError
      }
    },
    [applyTokens, logout],
  )

  useEffect(() => {
    const stored = readStoredTokens()
    if (stored) {
      applyTokens(stored)
      setStatus(MOCK_MODE ? 'authenticated' : 'checking')
    }
    bootstrappedRef.current = true
    return () => {
      clearRefreshTimer()
    }
  }, [applyTokens, clearRefreshTimer])

  useEffect(() => {
    if (!accessToken) {
      clearRefreshTimer()
      return
    }
    const exp = decodeJwtExpiration(accessToken)
    if (!exp) {
      return
    }
    const expiresInMs = exp * 1000 - Date.now()
    const refreshIn = Math.max(expiresInMs - REFRESH_LEEWAY_MS, 5_000)
    clearRefreshTimer()
    refreshTimeoutRef.current = setTimeout(() => {
      void refreshAccessToken()
    }, refreshIn)
    return () => {
      clearRefreshTimer()
    }
  }, [accessToken, clearRefreshTimer, refreshAccessToken])

  useEffect(() => {
    setApiAccessToken(accessToken)
  }, [accessToken])

  useEffect(() => {
    setApiRefreshHandler(async () => refreshAccessToken())
    return () => {
      setApiRefreshHandler(undefined)
    }
  }, [refreshAccessToken])

  useEffect(() => {
    setApiUnauthorizedHandler(() => {
      logout()
    })
    return () => {
      setApiUnauthorizedHandler(undefined)
    }
  }, [logout])

  useEffect(() => {
    if (!bootstrappedRef.current) {
      return
    }

    if (MOCK_MODE) {
      if (!accessToken) {
        setStatus('idle')
      }
      return
    }

    if (status !== 'checking') {
      return
    }

    let cancelled = false
    const controller = new AbortController()

    const validateSession = async () => {
      try {
        setStatusMessage('Confirming your access…')
        await Promise.all([
          apiClient.get('/health/', { skipAuth: true, signal: controller.signal }),
          apiClient.get('/me/', { signal: controller.signal }),
        ])
        if (!cancelled) {
          setStatus('authenticated')
          setError(undefined)
          setStatusMessage(undefined)
        }
      } catch (validationError) {
        if (cancelled) {
          return
        }
        console.error('Session validation failed', validationError)
        const message =
          validationError instanceof Error
            ? validationError.message
            : 'Unable to verify your session.'
        logout()
        setStatus('error')
        setError(message)
        setStatusMessage(undefined)
      }
    }

    void validateSession()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [status, logout, accessToken])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      isAuthenticated: status === 'authenticated',
      accessToken,
      tenantId,
      user,
      error,
      login,
      logout,
      statusMessage,
    }),
    [status, accessToken, tenantId, user, error, login, logout, statusMessage],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
