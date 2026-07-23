/**
 * LC-FE-02 AuthContext / AppContext (PAT-FE-03).
 *
 * Holds the two pieces of client state most screens need: whether we are
 * authenticated, and which event is selected. The frontend never holds a token
 * (the session is an HttpOnly cookie, FE-52); "authenticated" is just a flag we set
 * on login success and clear when any request 401s (onUnauthorized, PAT-FE-11).
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

interface AuthState {
  authenticated: boolean
  userId: string | null
  selectedEventId: string | null
  onLogin: (userId: string) => void
  onLogout: () => void
  onUnauthorized: () => void
  selectEvent: (eventId: string | null) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [authenticated, setAuthenticated] = useState(false)
  const [userId, setUserId] = useState<string | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)

  const onLogin = useCallback((id: string) => {
    setAuthenticated(true)
    setUserId(id)
  }, [])

  const clear = useCallback(() => {
    setAuthenticated(false)
    setUserId(null)
    setSelectedEventId(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      authenticated,
      userId,
      selectedEventId,
      onLogin,
      onLogout: clear,
      onUnauthorized: clear, // FE-50: a 401 anywhere returns us to anonymous
      selectEvent: setSelectedEventId,
    }),
    [authenticated, userId, selectedEventId, onLogin, clear],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (ctx === null) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
