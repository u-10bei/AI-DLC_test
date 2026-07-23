/**
 * V-05 Sufficiency (US-13). Shows the available / unavailable / undeclared / required
 * / shortage counts; a positive shortage is highlighted.
 */

import { useQuery } from '@tanstack/react-query'

import type { SufficiencyResponse } from '../api/types'
import { useApi } from '../app/apiContext'
import { useAuth } from '../app/AuthContext'
import { EmptyState, ErrorBanner, LoadingIndicator } from '../components/Feedback'

export function SufficiencyView(): JSX.Element {
  const api = useApi()
  const { selectedEventId } = useAuth()

  const query = useQuery<SufficiencyResponse>({
    queryKey: ['sufficiency', selectedEventId],
    enabled: selectedEventId !== null,
    queryFn: () => api.getJson<SufficiencyResponse>(`/events/${selectedEventId ?? ''}/sufficiency`),
  })

  if (selectedEventId === null) {
    return (
      <main className="sufficiency-view">
        <h1>充足状況</h1>
        <EmptyState>先にイベントを選択してください。</EmptyState>
      </main>
    )
  }

  return (
    <main className="sufficiency-view">
      <h1>充足状況（{selectedEventId}）</h1>
      {query.isLoading && <LoadingIndicator />}
      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && (
        <table data-testid="sufficiency-table">
          <tbody>
            <tr>
              <th scope="row">従事可</th>
              <td data-testid="sufficiency-available">{query.data.available}</td>
            </tr>
            <tr>
              <th scope="row">従事不可</th>
              <td>{query.data.unavailable}</td>
            </tr>
            <tr>
              <th scope="row">未申告</th>
              <td>{query.data.undeclared}</td>
            </tr>
            <tr>
              <th scope="row">必要数</th>
              <td>{query.data.required}</td>
            </tr>
            <tr>
              <th scope="row">不足数</th>
              <td data-testid="sufficiency-shortage">
                {query.data.shortage > 0 ? (
                  <strong className="shortage-warning">{query.data.shortage}</strong>
                ) : (
                  query.data.shortage
                )}
              </td>
            </tr>
          </tbody>
        </table>
      )}
    </main>
  )
}
