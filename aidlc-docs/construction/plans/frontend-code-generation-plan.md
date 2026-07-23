# U-08 frontend — Code Generation 計画（Part 1: Planning）

**ユニット**: U-08 frontend（最終ユニット、8/8）
**スタック**: React 18 + TypeScript(strict) + Vite / TanStack Query + Context / CSS Modules / fast-check / Vitest + Testing Library。
**この計画が Code Generation の唯一の真実の源**。各ステップ完了ごとに [x]。

---

## 1. ユニット文脈

- **依存**: U-07 の REST API のみ（NFR-M05）。バックエンドユニットを import しない（**H-5**、ESLint 境界で強制）。
- **消費エンドポイント**: 機能設計 `business-logic-model.md` §0 の表。
- **担当ストーリー（UI 部分）**: US-01（ログイン）, US-05（イベント）, US-07/08/09（マスタ取込）, US-11（申告）, US-13（充足）, US-16/17/20/24（最適化）, US-21/22（割当・手動修正）。
- **繰り越し（画面化しない）**: US-06/12/25/26/27/28（機能設計 §0）。

### 環境確認
- node v22 / npm 10 は利用可能。フロントのゲート（`tsc`/`eslint`/`vitest`）は本ステージで実行を試みる。**`npm install` がネットワーク不通で失敗する場合、フロントのゲートは Build and Test ステージで実行する**旨を記録する（バックエンドの Python ゲートは本ステージで必ず実行）。

---

## 2. ディレクトリ構成（決定）

`src/frontend/` を**自己完結した npm プロジェクトルート**とする（独自の `package.json`/`tsconfig`/`vite.config` を持つため、リポジトリの `src/`・`tests/` 分割規約には従わず、プロジェクト内に `src/` と `tests/` を持つ）。この逸脱は TS/npm プロジェクトの標準構成に合わせるための意図的判断（**U08-H5** として記録）。

```text
src/frontend/
├── package.json, tsconfig.json, vite.config.ts, eslint.config.js, index.html, .gitignore
├── src/
│   ├── api/         types.ts（DTO 写像）, client.ts（ApiClient）, converters.ts
│   ├── app/         AppShell.tsx, AuthContext.tsx, queryClient.ts, ErrorBoundary.tsx, routes.tsx, main.tsx
│   ├── components/  共通 Presentational（ErrorBanner, LoadingIndicator, EmptyState, CsvImportPanel, ...）
│   ├── views/       V-01..V-07 の Container
│   ├── hooks/       useJobStatus（ポーリング）等
│   └── styles/      *.module.css, global.css
└── tests/           *.test.ts(x)（Vitest + Testing Library + fast-check）
```

---

## 3. 生成ステップ（順次、完了ごとに [x]）

### バックエンド追加（U08-H1 / U08-H4 — Python、4 ゲートを緑に保つ）

- [x] **Step 1: U-07 に施設・小学校区の import/export エンドポイントを追加（U08-H1）**
  - `src/api_orchestration/services.py` / `routers.py` に `POST/GET /masters/facilities/import,export`、`POST/GET /masters/districts/import,export` を追加。U-03 の既存 `import_facilities`/`export_facilities`/`import_school_districts`/`export_school_districts` に配線。認可は職員と対称（IMPORT_MASTER / EXPORT_DATA）。エクスポートは `sanitize_csv_cell` を注入（U06-H3、職員と同様）。
  - `tests/api_orchestration/` に例示テスト追加（取込 200/行エラー、エクスポートのサニタイズ）。
  - **ストーリー**: US-08, US-09

- [x] **Step 2: U-07 に静的アセット配信をマウント（U08-H4）**
  - `composition.py`（または専用モジュール）で、`src/frontend/dist` が存在する場合のみ FastAPI `StaticFiles` をマウント（存在しなければ何もしない＝テスト環境・未ビルド時に壊れない）。SPA フォールバック（index.html）を配慮。
  - NFR-M05 を侵さない（静的配信と REST 通信は別物、プロセス内のドメイン共有なし）。
  - **ストーリー**: 基盤

### フロントエンド生成（src/frontend/）

- [x] **Step 3: プロジェクト雛形と品質ゲート設定**
  - `package.json`（React 18, TanStack Query, react-router, 開発: vite, typescript, vitest, @testing-library/react, @testing-library/jest-dom, fast-check, eslint + plugins, jsdom）、`tsconfig.json`（strict: true）、`vite.config.ts`、`index.html`、`.gitignore`。
  - `eslint.config.js`: **`no-restricted-imports` でバックエンド（`../../*`、リポジトリ `src/` 配下）への import を禁止（H-5、PAT-FE-14）**、`react/no-danger`（PAT-FE-12）を有効化。
  - **ストーリー**: 基盤

- [x] **Step 4: api レイヤ（LC-FE-01/05）**
  - `api/types.ts`: U-07 の DTO に対応する TS 型（`dto.py` を写す）。
  - `api/client.ts`: `fetch` ラッパ。`credentials:'include'`、`401` 捕捉→失効通知、非 2xx→型付き `ErrorResponse`、CSV 生バイト送受信。
  - `api/converters.ts`: DTO↔ビューモデルの純関数（fast-check 対象）。
  - **ストーリー**: 全般

- [x] **Step 5: app レイヤ（LC-FE-02/03/06）**
  - `AuthContext.tsx`（認証状態・選択中イベント・`onUnauthorized`）、`queryClient.ts`（TanStack Query、リトライ無効=fail-closed）、`ErrorBoundary.tsx`、`routes.tsx`、`AppShell.tsx`（Header/NavSidebar）、`main.tsx`。
  - **ストーリー**: US-01

- [x] **Step 6: 共通コンポーネント（Presentational）**
  - `ErrorBanner`, `LoadingIndicator`, `EmptyState`, `CsvImportPanel`（+ `RowErrorList`/`ImportResultBanner`）。`data-testid` を付与。
  - **ストーリー**: 全般

- [x] **Step 7: 画面（Container）V-01..V-07**
  - V-01 Login, V-02 Event, V-03 Masters（職員/施設/小学校区）, V-04 Declarations, V-05 Sufficiency, V-06 Optimize（+ `useJobStatus` ポーリング、PAT-FE-02）, V-07 Assignments（一覧 + 手動修正 + ViolationList）。
  - クライアント検証 FE-01〜42、`data-testid` 付与、`aria-live` でジョブ状態通知。
  - **注（U08-H2）**: V-07 の移動負担表示は `AssignmentResponse` 拡張が未了のため、当面 V-06 由来の `objective_value`/`optimality_gap` を要約表示（承認済みの範囲）。
  - **ストーリー**: US-05/07/08/09/11/13/16/17/20/21/22/24

- [x] **Step 8: スタイリング（CSS Modules、PAT-FE-40）**
  - 画面ごとの `*.module.css` + `global.css`。WCAG 2.1 AA のコントラスト・フォーカス可視化。
  - **ストーリー**: 基盤（NFR-FE-U2）

- [x] **Step 9: テスト（Vitest + Testing Library + fast-check）**
  - コンポーネントテスト（API モック）: 401→ログイン遷移、400→違反表示、CSV 行エラー表示、ジョブ投入→ポーリング→完了、手動修正の制約違反表示。
  - fast-check PBT: DTO↔ビューモデル写像のラウンドトリップ、フォーム検証プロパティ（全重み 0 は無効、負値は無効）。
  - **ストーリー**: 全般（PBT 拡張ブロッキング適合）

- [x] **Step 10: H-5 非空虚性 + フロントゲート**
  - `npm install` を試行。成功時: `tsc --noEmit`、`eslint`、`vitest run` を実行し緑にする。**H-5 非空虚性**（バックエンド import を注入→eslint FAIL、除去→PASS）を確認。
  - `npm install` 失敗（ネットワーク不通）時: 生成物はそのまま残し、フロントゲートは **Build and Test で実行**する旨を記録。
  - **ストーリー**: 品質ゲート

### ドキュメント + バックエンド回帰

- [x] **Step 11: 実装サマリ**
  - `aidlc-docs/construction/frontend/code/implementation-summary.md`（生成物・逸脱・申し送りの記録）。

- [x] **Step 12: バックエンド 4 ゲート回帰**
  - Step 1/2 の U-07 追加後、`pytest`（U-01〜U-07 回帰なし + 新規）、`mypy --strict`、`ruff`、`lint-imports`（14 契約 kept、施設/小学校区追加後も R-8 等維持）を緑にする。
  - **ストーリー**: 品質ゲート

---

## 4. 想定スコープ

- **新規（フロント）**: `src/frontend/` 一式（雛形 + api/app/components/views/hooks/styles + tests）。
- **修正（バックエンド, in-place）**: `src/api_orchestration/{routers.py, services.py, composition.py}`（U08-H1/H4）、`tests/api_orchestration/`（施設/小学校区テスト）。
- **新規ドキュメント**: `aidlc-docs/construction/frontend/code/implementation-summary.md`。
- **12 ステップ**。バックエンド 4 ゲート緑 + フロントゲート（実行可能な範囲で）緑で完了。

## 5. 申し送り（継続 + 新規）

- U08-H1（本計画 Step 1 で実施）、U08-H2（`AssignmentResponse` 移動指標、当面は未拡張で承認済み）、U08-H3（比較画面は U05-H6 後）、U08-H4（本計画 Step 2 で実施）、**U08-H5（`src/frontend/` は自己完結 npm プロジェクトのためリポジトリ `src/`・`tests/` 分割規約から逸脱）**、H-5（Step 3/10 で ESLint 強制 + 非空虚性確認）。
