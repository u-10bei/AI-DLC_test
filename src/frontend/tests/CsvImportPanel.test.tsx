import userEvent from '@testing-library/user-event'
import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CsvImportPanel } from '../src/components/CsvImportPanel'
import { mockFetchOnce, renderWithProviders } from './renderWithProviders'

afterEach(() => vi.restoreAllMocks())

const panel = (
  <CsvImportPanel label="職員マスタ" importPath="/masters/staff/import" testIdPrefix="masters-staff" />
)

describe('CsvImportPanel', () => {
  it('reports the success count on a 200 (FE-23)', async () => {
    mockFetchOnce(200, { success_count: 3 })
    renderWithProviders(panel)

    const file = new File(['職員ID\nS1\n'], 'staff.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByTestId('masters-staff-file'), file)
    await userEvent.click(screen.getByTestId('masters-staff-import'))

    await waitFor(() => expect(screen.getByTestId('masters-staff-success')).toHaveTextContent('3 件'))
  })

  it('lists row errors with line numbers on a 400 (FE-22)', async () => {
    mockFetchOnce(400, {
      message: '取り込みに失敗しました',
      violated_rule: null,
      errors: [{ line: 2, message: '居住小学校区IDが存在しません' }],
      violations: null,
    })
    renderWithProviders(panel)

    const file = new File(['職員ID\nS1\n'], 'staff.csv', { type: 'text/csv' })
    await userEvent.upload(screen.getByTestId('masters-staff-file'), file)
    await userEvent.click(screen.getByTestId('masters-staff-import'))

    await waitFor(() => expect(screen.getByTestId('row-error-list')).toHaveTextContent('2 行目'))
  })
})
