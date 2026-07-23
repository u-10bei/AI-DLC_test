import userEvent from '@testing-library/user-event'
import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LoginView } from '../src/views/LoginView'
import { mockFetchOnce, renderWithProviders } from './renderWithProviders'

afterEach(() => vi.restoreAllMocks())

describe('LoginView', () => {
  it('shows a generic message on 401 and does not reveal account existence (FE-03)', async () => {
    mockFetchOnce(401, { message: '認証に失敗しました' })
    renderWithProviders(<LoginView />)

    await userEvent.type(screen.getByTestId('login-user-id'), 'C001')
    await userEvent.type(screen.getByTestId('login-password'), 'wrong')
    await userEvent.click(screen.getByTestId('login-submit'))

    await waitFor(() => expect(screen.getByTestId('login-error')).toHaveTextContent('認証に失敗しました'))
  })

  it('blocks submission and shows field errors when fields are empty (FE-01/02)', async () => {
    const fetchSpy = vi.fn()
    ;(globalThis as { fetch: typeof fetch }).fetch = fetchSpy as unknown as typeof fetch
    renderWithProviders(<LoginView />)

    await userEvent.click(screen.getByTestId('login-submit'))

    expect(screen.getByTestId('login-field-error-user_id')).toBeInTheDocument()
    expect(fetchSpy).not.toHaveBeenCalled() // never hit the backend
  })
})
