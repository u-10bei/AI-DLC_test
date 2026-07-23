/**
 * Shared presentational feedback components (LC-FE-06 surface): error, loading and
 * empty states. All text is rendered as text (no dangerouslySetInnerHTML, PAT-FE-12);
 * backend messages are shown verbatim (PAT-FE-13).
 */

import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { ConstraintViolationResponse, RowErrorResponse } from '../api/types'

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }): JSX.Element {
  const message = error instanceof ApiError ? error.message : 'エラーが発生しました'
  return (
    <div role="alert" className="banner banner-error" data-testid="error-banner">
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} data-testid="error-banner-retry">
          再試行
        </button>
      )}
    </div>
  )
}

export function LoadingIndicator({ label = '読み込み中…' }: { label?: string }): JSX.Element {
  return (
    <p role="status" aria-live="polite" data-testid="loading-indicator">
      {label}
    </p>
  )
}

export function EmptyState({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="empty-state" data-testid="empty-state">
      {children}
    </p>
  )
}

export function RowErrorList({ errors }: { errors: RowErrorResponse[] }): JSX.Element {
  return (
    <ul className="row-error-list" data-testid="row-error-list">
      {errors.map((e) => (
        <li key={`${e.line}-${e.message}`}>
          {e.line} 行目: {e.message}
        </li>
      ))}
    </ul>
  )
}

export function ViolationList({ violations }: { violations: ConstraintViolationResponse[] }): JSX.Element {
  return (
    <ul className="violation-list" role="alert" data-testid="violation-list">
      {violations.map((v, i) => (
        <li key={`${v.constraint_id}-${i}`}>
          [{v.constraint_id}] {v.detail}
          {v.facility_id ? ` (施設: ${v.facility_id})` : ''}
          {v.staff_id ? ` (職員: ${v.staff_id})` : ''}
        </li>
      ))}
    </ul>
  )
}
