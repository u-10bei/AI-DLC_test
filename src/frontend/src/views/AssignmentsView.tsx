/**
 * V-07 Assignments (US-21/22). Lists assignments and allows a manual edit. The edit
 * posts to PATCH and shows the backend's constraint violations on a 400 (FE-41) — the
 * frontend never judges C1..C5 itself; U-04 owns that (U07-H1).
 *
 * Value display (U08-H2): AssignmentResponse does not yet carry per-assignment travel
 * time/cost, so the near-vs-far burden cannot be shown numerically here. Until that
 * enrichment lands, the value signal is the optimization result (objective / gap) from
 * V-06. This is the approved interim behaviour.
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/client'
import { fromAssignmentResponse } from '../api/converters'
import type { AssignmentResponse, ConstraintViolationResponse } from '../api/types'
import { validateAssignmentPatch, type FieldError } from '../api/validation'
import { useApi } from '../app/apiContext'
import { useAuth } from '../app/AuthContext'
import { EmptyState, ErrorBanner, LoadingIndicator, ViolationList } from '../components/Feedback'

export function AssignmentsView(): JSX.Element {
  const api = useApi()
  const queryClient = useQueryClient()
  const { selectedEventId } = useAuth()
  const [staffId, setStaffId] = useState('')
  const [facilityId, setFacilityId] = useState('')
  const [errors, setErrors] = useState<FieldError[]>([])
  const [violations, setViolations] = useState<ConstraintViolationResponse[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['assignments', selectedEventId],
    enabled: selectedEventId !== null,
    queryFn: () => api.getJson<AssignmentResponse[]>(`/events/${selectedEventId ?? ''}/assignments`),
  })

  const mutation = useMutation({
    mutationFn: (): Promise<AssignmentResponse[]> =>
      api.patchJson<AssignmentResponse[]>(`/events/${selectedEventId ?? ''}/assignments`, {
        staff_id: staffId,
        facility_id: facilityId,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['assignments', selectedEventId], updated)
      setViolations(null)
      setMessage(null)
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setMessage(err.message)
        setViolations(err.body?.violations ?? null)
      } else {
        setMessage('修正に失敗しました')
      }
    },
  })

  function submit(e: React.FormEvent): void {
    e.preventDefault()
    const found = validateAssignmentPatch(staffId, facilityId)
    setErrors(found)
    if (found.length === 0) mutation.mutate()
  }

  if (selectedEventId === null) {
    return (
      <main className="assignments-view">
        <h1>割当結果</h1>
        <EmptyState>先にイベントを選択してください。</EmptyState>
      </main>
    )
  }

  const assignments = (query.data ?? []).map(fromAssignmentResponse)

  return (
    <main className="assignments-view">
      <h1>割当結果（{selectedEventId}）</h1>
      {query.isLoading && <LoadingIndicator />}
      {query.isError && <ErrorBanner error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && assignments.length === 0 && <EmptyState>割当がありません。</EmptyState>}
      {assignments.length > 0 && (
        <table data-testid="assignments-table">
          <thead>
            <tr>
              <th scope="col">職員ID</th>
              <th scope="col">施設ID</th>
              <th scope="col">確定</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={`${a.staffId}-${a.facilityId}`}>
                <td>{a.staffId}</td>
                <td>{a.facilityId}</td>
                <td>{a.isPinned ? '確定' : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>手動修正</h2>
      <form onSubmit={submit} data-testid="assignment-edit-form" noValidate>
        <label htmlFor="edit-staff">職員ID</label>
        <input id="edit-staff" value={staffId} onChange={(e) => setStaffId(e.target.value)} data-testid="assignment-staff-id" />
        <label htmlFor="edit-facility">施設ID</label>
        <input id="edit-facility" value={facilityId} onChange={(e) => setFacilityId(e.target.value)} data-testid="assignment-facility-id" />
        <button type="submit" disabled={mutation.isPending} data-testid="assignment-submit">
          割当を変更
        </button>
      </form>

      {errors.map((err) => (
        <p key={err.field} role="alert" data-testid={`assignment-field-error-${err.field}`}>
          {err.message}
        </p>
      ))}
      {message && (
        <p role="alert" data-testid="assignment-error">
          {message}
        </p>
      )}
      {violations && <ViolationList violations={violations} />}
    </main>
  )
}
