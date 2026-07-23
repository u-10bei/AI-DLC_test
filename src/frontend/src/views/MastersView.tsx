/**
 * V-03 Masters (US-07/08/09). Three symmetric CSV panels. Facilities and school
 * districts reach real endpoints thanks to U08-H1; staff was already there.
 */

import { CsvImportPanel } from '../components/CsvImportPanel'

export function MastersView(): JSX.Element {
  return (
    <main className="masters-view">
      <h1>マスタ管理</h1>
      <p>小学校区 → 施設 → 職員 の順に取り込んでください（施設は小学校区を参照します）。</p>
      <CsvImportPanel
        label="小学校区マスタ"
        importPath="/masters/districts/import"
        exportPath="/masters/districts/export"
        testIdPrefix="masters-districts"
      />
      <CsvImportPanel
        label="施設マスタ"
        importPath="/masters/facilities/import"
        exportPath="/masters/facilities/export"
        testIdPrefix="masters-facilities"
      />
      <CsvImportPanel
        label="職員マスタ"
        importPath="/masters/staff/import"
        exportPath="/masters/staff/export"
        testIdPrefix="masters-staff"
      />
    </main>
  )
}
