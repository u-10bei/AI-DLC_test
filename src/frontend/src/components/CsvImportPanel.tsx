/**
 * Shared CSV import + export panel (used by masters and declarations, FE-20..23).
 *
 * The frontend does not parse or validate the CSV — it posts the raw bytes and shows
 * whatever the backend reports (success_count, or a 400 with row errors). FE-21.
 */

import { useState } from 'react'

import { ApiError } from '../api/client'
import { useApi } from '../app/apiContext'
import type { RowErrorResponse } from '../api/types'
import { RowErrorList } from './Feedback'

interface Props {
  label: string
  importPath: string
  exportPath?: string
  testIdPrefix: string
  onImported?: () => void
}

export function CsvImportPanel({ label, importPath, exportPath, testIdPrefix, onImported }: Props): JSX.Element {
  const api = useApi()
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [successCount, setSuccessCount] = useState<number | null>(null)
  const [rowErrors, setRowErrors] = useState<RowErrorResponse[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function upload(): Promise<void> {
    if (file === null) return
    setBusy(true)
    setSuccessCount(null)
    setRowErrors(null)
    setMessage(null)
    try {
      const result = await api.postCsv(importPath, file)
      setSuccessCount(result.success_count)
      onImported?.()
    } catch (err) {
      if (err instanceof ApiError) {
        setMessage(err.message)
        setRowErrors(err.body?.errors ?? null)
      } else {
        setMessage('取り込みに失敗しました')
      }
    } finally {
      setBusy(false)
    }
  }

  async function download(): Promise<void> {
    if (!exportPath) return
    const text = await api.getText(exportPath)
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${testIdPrefix}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="csv-panel" data-testid={`${testIdPrefix}-panel`}>
      <h3>{label}</h3>
      <input
        type="file"
        accept=".csv,text/csv"
        aria-label={`${label} CSVファイル`}
        data-testid={`${testIdPrefix}-file`}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <button
        type="button"
        disabled={file === null || busy}
        onClick={() => void upload()}
        data-testid={`${testIdPrefix}-import`}
      >
        取り込む
      </button>
      {exportPath && (
        <button type="button" onClick={() => void download()} data-testid={`${testIdPrefix}-export`}>
          エクスポート
        </button>
      )}
      {successCount !== null && (
        <p role="status" data-testid={`${testIdPrefix}-success`}>
          {successCount} 件取り込みました
        </p>
      )}
      {message && (
        <p role="alert" data-testid={`${testIdPrefix}-error`}>
          {message}
        </p>
      )}
      {rowErrors && <RowErrorList errors={rowErrors} />}
    </section>
  )
}
