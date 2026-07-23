/**
 * V-04 Declarations import (US-11). Requires a selected event; the declarations CSV
 * is posted to that event.
 */

import { useAuth } from '../app/AuthContext'
import { CsvImportPanel } from '../components/CsvImportPanel'
import { EmptyState } from '../components/Feedback'

export function DeclarationsView(): JSX.Element {
  const { selectedEventId } = useAuth()

  if (selectedEventId === null) {
    return (
      <main className="declarations-view">
        <h1>従事可否申告の取り込み</h1>
        <EmptyState>先にイベントを作成・選択してください。</EmptyState>
      </main>
    )
  }

  return (
    <main className="declarations-view">
      <h1>従事可否申告の取り込み（{selectedEventId}）</h1>
      <CsvImportPanel
        label="従事可否申告"
        importPath={`/events/${selectedEventId}/declarations/import`}
        testIdPrefix="declarations"
      />
    </main>
  )
}
