/**
 * L-00 AppShell: header (current user + logout) and nav, wrapping the routed screen.
 * Unauthenticated users only ever see the login route (guard below).
 */

import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'

import { useApi } from './apiContext'
import { useAuth } from './AuthContext'

const NAV = [
  { to: '/events', label: 'イベント' },
  { to: '/masters', label: 'マスタ' },
  { to: '/declarations', label: '申告取込' },
  { to: '/sufficiency', label: '充足状況' },
  { to: '/optimize', label: '最適化' },
  { to: '/assignments', label: '割当結果' },
]

export function AppShell(): JSX.Element {
  const auth = useAuth()
  const api = useApi()
  const navigate = useNavigate()

  if (!auth.authenticated) {
    return <Navigate to="/login" replace />
  }

  async function logout(): Promise<void> {
    try {
      await api.deleteEmpty('/sessions')
    } finally {
      auth.onLogout()
      navigate('/login')
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">居住地考慮型 従事者割当最適化システム</span>
        <span className="app-user" data-testid="current-user">
          {auth.userId}
        </span>
        <button type="button" onClick={() => void logout()} data-testid="logout-button">
          ログアウト
        </button>
      </header>
      <div className="app-body">
        <nav className="app-nav" aria-label="メインナビゲーション">
          <ul>
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} data-testid={`nav-${item.to.slice(1)}`}>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="app-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
