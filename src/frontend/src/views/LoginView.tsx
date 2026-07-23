/**
 * V-01 Login (US-01). A 401 shows a generic message that never reveals whether the
 * account exists (FE-03 / BR-SEC04). On success the cookie is set by the backend and
 * we flip the auth flag.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { validateLogin, type FieldError } from '../api/validation'
import { useApi } from '../app/apiContext'
import { useAuth } from '../app/AuthContext'

export function LoginView(): JSX.Element {
  const api = useApi()
  const auth = useAuth()
  const navigate = useNavigate()
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldError[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    const found = validateLogin(userId, password)
    setErrors(found)
    if (found.length > 0) return
    setBusy(true)
    setMessage(null)
    try {
      await api.postEmpty('/sessions', { user_id: userId, password })
      auth.onLogin(userId)
      navigate('/events')
    } catch (err) {
      // FE-03: same generic message regardless of the reason.
      setMessage(err instanceof ApiError ? err.message : '認証に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-view">
      <h1>ログイン</h1>
      <form onSubmit={(e) => void submit(e)} data-testid="login-form" noValidate>
        <label htmlFor="user_id">ユーザーID</label>
        <input
          id="user_id"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          data-testid="login-user-id"
        />
        <label htmlFor="password">パスワード</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          data-testid="login-password"
        />
        <button type="submit" disabled={busy} data-testid="login-submit">
          ログイン
        </button>
      </form>
      {errors.map((err) => (
        <p key={err.field} role="alert" data-testid={`login-field-error-${err.field}`}>
          {err.message}
        </p>
      ))}
      {message && (
        <p role="alert" data-testid="login-error">
          {message}
        </p>
      )}
    </main>
  )
}
