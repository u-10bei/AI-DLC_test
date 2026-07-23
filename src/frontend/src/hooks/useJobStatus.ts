/**
 * LC-FE-04 job-status polling (PAT-FE-02).
 *
 * Polls GET /optimizations/{jobId} every ~2s (Q4=A) and STOPS the moment the job
 * reaches a terminal state — the refetchInterval returns false, so the timer is torn
 * down rather than left running. Leaving the screen deactivates the query, which also
 * stops polling; returning with the same jobId resumes.
 */

import { useQuery } from '@tanstack/react-query'

import { useApi } from '../app/apiContext'
import type { JobState, JobStatusResponse } from '../api/types'
import { TERMINAL_STATES } from '../api/types'

const POLL_MS = 2000

export function isTerminal(state: string): boolean {
  return (TERMINAL_STATES as readonly string[]).includes(state)
}

export function useJobStatus(jobId: string | null) {
  const api = useApi()
  return useQuery<JobStatusResponse>({
    queryKey: ['job', jobId],
    enabled: jobId !== null,
    queryFn: () => api.getJson<JobStatusResponse>(`/optimizations/${jobId ?? ''}`),
    refetchInterval: (query) => {
      const state = query.state.data?.state
      return state && isTerminal(state) ? false : POLL_MS
    },
  })
}

export function jobStateLabel(state: string): string {
  const labels: Record<JobState, string> = {
    QUEUED: '待機中',
    RUNNING: '計算中',
    SUCCEEDED: '完了',
    INFEASIBLE: '実行不能（人員不足）',
    FAILED: '失敗',
  }
  return labels[state as JobState] ?? state
}
