# U-08 frontend — フロントエンドコンポーネント設計（機能設計 主成果物）

**技術非依存**: 論理コンポーネントとして定義する（React/Vue 等の特定 API に依存しない）。フレームワークは NFR Requirements で決定。
**分類**: **Container**（状態・API 呼び出しを持つ）と **Presentational**（props を受けて描画のみ）に分ける（ステップ B）。

---

## 1. コンポーネント階層

```text
App (Container)
├── AppShell (L-00, Container)                 選択中イベント・認証状態を保持
│   ├── Header (Presentational)                ログイン中ユーザ表示 + ログアウト
│   ├── NavSidebar (Presentational)            画面遷移・イベント選択
│   └── <現在の画面をここに描画>
│
├── LoginView (V-01, Container)
│   └── LoginForm (Presentational)
│
├── EventView (V-02, Container)
│   ├── EventCreateForm (Presentational)
│   └── EventSummaryCard (Presentational)
│
├── MastersView (V-03, Container)
│   └── CsvImportPanel × 3 (Presentational)    職員 / 施設 / 小学校区
│       └── ImportResultBanner / RowErrorList (Presentational)
│
├── DeclarationsView (V-04, Container)
│   └── CsvImportPanel (Presentational)         申告
│
├── SufficiencyView (V-05, Container)
│   └── SufficiencyPanel (Presentational)       充足/不足の数値
│
├── OptimizeView (V-06, Container)              ジョブポーリングの所有者
│   ├── OptimizationParamForm (Presentational)
│   └── JobProgressPanel (Presentational)       state/ギャップ/経過/診断
│
├── AssignmentsView (V-07, Container)
│   ├── AssignmentTable (Presentational)        一覧 + ピン表示
│   ├── AssignmentEditForm (Presentational)     手動修正
│   └── ViolationList (Presentational)          400 の制約違反表示
│
└── 共通 (Presentational)
    ├── ErrorBanner                             400/403/404/5xx の汎用表示
    ├── LoadingIndicator
    └── EmptyState
```

**横断関心**:
- **ApiClient**（Container 群が使う薄いモジュール）: ベース URL を外部化設定から取得（NFR-M05/M03）、Cookie 自動送信、`401` を捕捉して `AppShell` に失効を通知（FE-50）。エラー応答（`ErrorResponse`）を型付きで返す。
- **AuthContext**（`AppShell` が提供）: 認証状態と「失効時に V-01 へ遷移」を全画面へ配布（FE-50/52）。

---

## 2. コンポーネントごとの props / state

### AppShell (Container)
- **state**: `selectedEventId: string | null`、`authState: 'anonymous' | 'authenticated'`
- **提供**: `selectEvent(id)`、`onUnauthorized()`（→ V-01 へ）
- **子への props**: `selectedEventId` を V-04〜V-07 に配布

### LoginView / LoginForm
- **local state**: `userId`, `password`, `submitting`, `errorMessage`
- **検証**: FE-01/02
- **API**: `POST /sessions` → 成功で `authState='authenticated'`、失敗（401）で FE-03 の汎用文言

### EventView / EventCreateForm / EventSummaryCard
- **local state**: `id, type(選択), name, scheduledDate, submitting`
- **fetch state**: 直近作成イベント（`GET /events/{id}`）
- **検証**: FE-10〜13
- **API**: `POST /events` → 201、`GET /events/{id}`

### MastersView / CsvImportPanel（職員・施設・小学校区）
- **props**（各パネル）: `kind: 'staff'|'facilities'|'districts'`、`importUrl`、`exportUrl`
- **local state**: `file`, `uploading`, `result: {successCount} | null`, `rowErrors: RowError[] | null`
- **検証**: FE-20〜23
- **API**: `POST /masters/{kind}/import`（生バイト）、`GET /masters/{kind}/export`
  - ※施設・小学校区は **U08-H1** で U-07 に追加（職員は既存）

### DeclarationsView
- **props**: `eventId`
- **local state**: `file, uploading, result, rowErrors`
- **API**: `POST /events/{eventId}/declarations/import`

### SufficiencyView / SufficiencyPanel
- **props**: `eventId`
- **fetch state**: `SufficiencyResponse`
- **描画**: 従事可/不可/未申告/必要数/不足数。`shortage > 0` で警告
- **API**: `GET /events/{eventId}/sufficiency`

### OptimizeView / OptimizationParamForm / JobProgressPanel
- **props**: `eventId`
- **local state**: パラメータ（mode, 重み3, time_limit, dept_cap）、`jobId`, `jobState`, `elapsed`, `polling`
- **fetch/poll state**: `JobStatusResponse`
- **検証**: FE-30〜35
- **API**: `POST /optimizations` → 202、以後 `GET /optimizations/{jobId}` を約2秒間隔でポーリング（Q4=A）
- **JobProgressPanel の描画**（state 別）:
  - QUEUED/RUNNING → 進捗表示 + 経過時間、「実行」無効化
  - SUCCEEDED → 割当件数・`objective_value`・`optimality_gap`・経過、V-07 へ誘導
  - INFEASIBLE → `detail`（不足診断、BR-API15）
  - FAILED → 汎用エラー（SECURITY-09）

### AssignmentsView / AssignmentTable / AssignmentEditForm / ViolationList
- **props**: `eventId`
- **fetch state**: `AssignmentResponse[]`
- **local state**: 編集対象 `staffId, facilityId`, `submitting`, `violations`
- **検証**: FE-40〜42
- **API**: `GET /events/{eventId}/assignments`、`PATCH /events/{eventId}/assignments`
  - 200 → 一覧を差し替え、400 → `ViolationList` に `violations` を表示
- **価値提示（U08-H2 に依存）**: 移動時間・費用を割当ごとに表示するには `AssignmentResponse` の拡張が必要。未拡張の場合は V-06 由来の `objective_value`/`optimality_gap` を要約表示する

---

## 3. API 連携マップ（コンポーネント → エンドポイント）

| コンポーネント | メソッド・パス | 送信 DTO | 受信 DTO | 主なエラー |
|--------------|--------------|---------|---------|-----------|
| LoginForm | `POST /sessions` | LoginRequest | （204, Cookie） | 401 → FE-03 |
| Header(logout) | `DELETE /sessions` | — | 204 | — |
| EventCreateForm | `POST /events` | EventRequest | EventResponse | 400(未知type), 422, 403 |
| EventSummaryCard | `GET /events/{id}` | — | EventResponse | 404 |
| CsvImportPanel(staff) | `POST /masters/staff/import` | 生CSV | ImportResultResponse | 400+errors[] |
| CsvImportPanel(staff) | `GET /masters/staff/export` | — | text/csv | 403 |
| CsvImportPanel(facilities)※ | `POST/GET /masters/facilities/import,export` | 生CSV | ImportResultResponse / csv | U08-H1 |
| CsvImportPanel(districts)※ | `POST/GET /masters/districts/import,export` | 生CSV | ImportResultResponse / csv | U08-H1 |
| DeclarationsView | `POST /events/{id}/declarations/import` | 生CSV | ImportResultResponse | 400+errors[] |
| SufficiencyPanel | `GET /events/{id}/sufficiency` | — | SufficiencyResponse | 403,404 |
| OptimizationParamForm | `POST /optimizations` | OptimizationRequest | JobAcceptedResponse | 400,422,403 |
| JobProgressPanel | `GET /optimizations/{job_id}` | — | JobStatusResponse | 404 |
| AssignmentTable | `GET /events/{id}/assignments` | — | AssignmentResponse[] | 403,404 |
| AssignmentEditForm | `PATCH /events/{id}/assignments` | AssignmentPatchRequest | AssignmentResponse[] | 400+violations |

※ U08-H1 で U-07 に追加するエンドポイント（U-03 のサービスは既存）。

---

## 4. ユーザ操作フロー（代替系を含む）

**ログイン**: 入力 → 送信 → 204 で `/events` へ / 401 で FE-03 表示、フォーム保持。

**マスタ取込**: ファイル選択 → アップロード → 成功で `success_count` / 400 で行別エラー一覧、ファイルは保持し再選択可。

**最適化**: パラメータ入力（FE-30〜34）→ 実行（ボタン無効化）→ ポーリング → 終端で結果/診断/エラー。QUEUED/RUNNING 中に画面離脱 → 再訪時 `jobId` があれば状態を再取得。

**手動修正**: 行を選択 → 職員/施設を変更 → PATCH → 200 で一覧更新 / 400 で `ViolationList`（制約 ID・詳細）、元の割当は変更しない。

**セッション失効（横断）**: 任意の操作中に 401 → 現操作を中断し V-01 へ、再ログイン後に案内。

---

## 5. テスト戦略の予告（Code Generation 向け）

- **コンポーネントテスト**: API をモックし、各 Container の状態遷移とエラー表示を検証（unit-of-work.md「API モックを用いたコンポーネントテスト」）。
- **UI フローテスト**: 価値実証フロー（ログイン→…→割当）を通しで検証。
- **PBT**（フロント側フレームワークは U01-H20 で繰り越し、NFR Requirements で決定）: DTO ↔ ビューモデルの写像やフォーム検証のプロパティを対象にしうる。詳細は U-08 の NFR で確定。
- **H-5 境界検証**: `src/frontend/` がバックエンドユニットを import しないことをリンタ／ビルドで機械検証（Code Generation で実装）。

---

## 6. 申し送りの再掲

- **U08-H1**: 施設・小学校区の import/export を U-07 に追加（V-03 の依存、U-03 サービスは既存）。
- **U08-H2**: 割当ごとの移動時間・費用の提示には `AssignmentResponse` 拡張が必要（V-07 の価値提示、承認時に確認）。
- **U08-H3**: 比較レポート画面は U05-H6 解消後（DTO/converter は実装済み）。
- **H-5**: フロント→バックエンド import 禁止の機械検証。
