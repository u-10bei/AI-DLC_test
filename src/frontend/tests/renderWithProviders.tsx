import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'

import { ApiClient } from '../src/api/client'
import { ApiContext } from '../src/app/apiContext'
import { AuthProvider } from '../src/app/AuthContext'

/** Render a view with all providers and an ApiClient whose fetch is mocked per test. */
export function renderWithProviders(
  ui: ReactNode,
  options: { route?: string; api?: ApiClient } = {},
): RenderResult {
  const api = options.api ?? new ApiClient({ baseUrl: '' })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <MemoryRouter initialEntries={[options.route ?? '/']}>
      <AuthProvider>
        <ApiContext.Provider value={api}>
          <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
        </ApiContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

/** A fetch stub returning a fixed status/body for the next call(s). */
export function mockFetchOnce(status: number, body: unknown): void {
  ;(globalThis as { fetch: typeof fetch }).fetch = () =>
    Promise.resolve(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
}
