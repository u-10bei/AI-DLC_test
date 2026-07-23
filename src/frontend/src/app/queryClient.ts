/**
 * LC-FE-03 QueryClient (PAT-FE-01/30).
 *
 * retry:false is deliberate — the project's posture is fail-closed with no automatic
 * retries (resiliency extension disabled, CQ4=A / PAT-FE-20). A failed request shows
 * an error and a manual retry, it does not silently re-attempt.
 */

import { QueryClient } from '@tanstack/react-query'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // fail-closed, no auto-retry (PAT-FE-20)
        refetchOnWindowFocus: false,
        staleTime: 5_000,
      },
      mutations: {
        retry: false,
      },
    },
  })
}
