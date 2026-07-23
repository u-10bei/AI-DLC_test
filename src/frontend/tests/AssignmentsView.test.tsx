/**
 * The manual edit shows the backend's constraint violations on a 400 and never judges
 * C1..C5 itself (FE-41 / U07-H1). We seed a selected event via the login flow-less
 * path by rendering with an event already chosen.
 */

import userEvent from '@testing-library/user-event'
import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiClient } from '../src/api/client'
import { ApiContext } from '../src/app/apiContext'
import { AuthProvider, useAuth } from '../src/app/AuthContext'
import { AssignmentsView } from '../src/views/AssignmentsView'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { useEffect, type ReactNode } from 'react'

afterEach(() => vi.restoreAllMocks())

function SelectEvent({ id, children }: { id: string; children: ReactNode }): JSX.Element {
  const { selectEvent } = useAuth()
  useEffect(() => selectEvent(id), [id, selectEvent])
  return <>{children}</>
}

function renderWithEvent(): void {
  const api = new ApiClient({ baseUrl: '' })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <MemoryRouter>
      <AuthProvider>
        <ApiContext.Provider value={api}>
          <QueryClientProvider client={qc}>
            <SelectEvent id="E1">
              <AssignmentsView />
            </SelectEvent>
          </QueryClientProvider>
        </ApiContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('AssignmentsView manual edit', () => {
  it('renders the backend constraint violations on a 400 (FE-41)', async () => {
    // First the GET assignments (empty list is fine), then the PATCH 400.
    const responses = [
      new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } }),
      new Response(
        JSON.stringify({
          message: 'assignment violates hard constraints',
          violations: [{ constraint_id: 'C1', detail: '施設F1の必要人数を超えています', facility_id: 'F1', staff_id: null }],
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      ),
    ]
    ;(globalThis as { fetch: typeof fetch }).fetch = (() =>
      Promise.resolve(responses.shift() as Response)) as unknown as typeof fetch

    renderWithEvent()

    await userEvent.type(screen.getByTestId('assignment-staff-id'), 'S3')
    await userEvent.type(screen.getByTestId('assignment-facility-id'), 'F1')
    await userEvent.click(screen.getByTestId('assignment-submit'))

    await waitFor(() => expect(screen.getByTestId('violation-list')).toHaveTextContent('C1'))
  })
})
