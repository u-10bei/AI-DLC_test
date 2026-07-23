/**
 * V-06 Optimize (US-16/17/20/24). Submits a job, then polls until a terminal state
 * (PAT-FE-02). The "実行" button is disabled while a non-terminal job is running
 * (FE-35). SUCCEEDED shows objective value + gap; INFEASIBLE shows the shortage
 * diagnosis; FAILED shows a generic error.
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'

import { DEFAULT_OPTIMIZATION_FORM, toOptimizationRequest, type OptimizationForm } from '../api/converters'
import type { JobAcceptedResponse, ReoptimizationMode } from '../api/types'
import { validateOptimizationForm, type FieldError } from '../api/validation'
import { useApi } from '../app/apiContext'
import { useAuth } from '../app/AuthContext'
import { EmptyState, ErrorBanner } from '../components/Feedback'
import { isTerminal, jobStateLabel, useJobStatus } from '../hooks/useJobStatus'

export function OptimizeView(): JSX.Element {
  const api = useApi()
  const { selectedEventId } = useAuth()
  const [form, setForm] = useState<OptimizationForm>(DEFAULT_OPTIMIZATION_FORM(selectedEventId ?? ''))
  const [errors, setErrors] = useState<FieldError[]>([])
  const [jobId, setJobId] = useState<string | null>(null)

  const job = useJobStatus(jobId)
  const running = jobId !== null && (job.data === undefined || !isTerminal(job.data.state))

  const mutation = useMutation({
    mutationFn: (): Promise<JobAcceptedResponse> =>
      api.postJson<JobAcceptedResponse>('/optimizations', toOptimizationRequest({ ...form, eventId: selectedEventId ?? '' })),
    onSuccess: (accepted) => setJobId(accepted.job_id),
  })

  function submit(e: React.FormEvent): void {
    e.preventDefault()
    const found = validateOptimizationForm(form)
    setErrors(found)
    if (found.length === 0) mutation.mutate()
  }

  function num(field: keyof OptimizationForm, value: string): void {
    setForm({ ...form, [field]: Number(value) })
  }

  if (selectedEventId === null) {
    return (
      <main className="optimize-view">
        <h1>割当最適化</h1>
        <EmptyState>先にイベントを選択してください。</EmptyState>
      </main>
    )
  }

  return (
    <main className="optimize-view">
      <h1>割当最適化（{selectedEventId}）</h1>
      <form onSubmit={submit} data-testid="optimize-form" noValidate>
        <label htmlFor="opt-mode">再最適化モード</label>
        <select
          id="opt-mode"
          value={form.mode}
          onChange={(e) => setForm({ ...form, mode: e.target.value as ReoptimizationMode })}
          data-testid="optimize-mode"
        >
          <option value="FULL">全体（FULL）</option>
          <option value="INCREMENTAL">増分（INCREMENTAL）</option>
        </select>

        <label htmlFor="opt-time-w">移動時間の重み</label>
        <input id="opt-time-w" type="number" step="0.1" value={form.travelTimeWeight}
          onChange={(e) => num('travelTimeWeight', e.target.value)} data-testid="optimize-time-weight" />

        <label htmlFor="opt-cost-w">移動費用の重み</label>
        <input id="opt-cost-w" type="number" step="0.1" value={form.travelCostWeight}
          onChange={(e) => num('travelCostWeight', e.target.value)} data-testid="optimize-cost-weight" />

        <label htmlFor="opt-ineq-w">不公平の重み</label>
        <input id="opt-ineq-w" type="number" step="0.1" value={form.inequityWeight}
          onChange={(e) => num('inequityWeight', e.target.value)} data-testid="optimize-inequity-weight" />

        <label htmlFor="opt-limit">制限時間（秒）</label>
        <input id="opt-limit" type="number" value={form.timeLimitSeconds}
          onChange={(e) => num('timeLimitSeconds', e.target.value)} data-testid="optimize-time-limit" />

        <label htmlFor="opt-cap">部署上限</label>
        <input id="opt-cap" type="number" value={form.departmentCapLimit}
          onChange={(e) => num('departmentCapLimit', e.target.value)} data-testid="optimize-dept-cap" />

        <button type="submit" disabled={running || mutation.isPending} data-testid="optimize-submit">
          実行
        </button>
      </form>

      {errors.map((err) => (
        <p key={err.field} role="alert" data-testid={`optimize-field-error-${err.field}`}>
          {err.message}
        </p>
      ))}
      {mutation.isError && <ErrorBanner error={mutation.error} />}

      {jobId && (
        <section aria-live="polite" data-testid="job-progress">
          <h2>ジョブ状態: <span data-testid="job-state">{job.data ? jobStateLabel(job.data.state) : '待機中'}</span></h2>
          {job.data?.state === 'SUCCEEDED' && (
            <dl data-testid="job-succeeded">
              <dt>割当件数</dt>
              <dd>{job.data.assignments?.length ?? 0}</dd>
              <dt>目的関数値</dt>
              <dd>{job.data.objective_value ?? '-'}</dd>
              <dt>最適性ギャップ</dt>
              <dd>{job.data.optimality_gap ?? '-'}</dd>
            </dl>
          )}
          {job.data?.state === 'INFEASIBLE' && (
            <p role="alert" data-testid="job-infeasible">
              実行不能: {job.data.detail ?? '人員が不足しています'}
            </p>
          )}
          {job.data?.state === 'FAILED' && (
            <p role="alert" data-testid="job-failed">
              計算に失敗しました。
            </p>
          )}
        </section>
      )}
    </main>
  )
}
