# U-08 frontend — 実装サマリ

**ユニット**: U-08 frontend（最終ユニット、8/8）
**日付**: 2026-07-23
**状態**: フロント 4 ゲート緑 + バックエンド 4 ゲート緑

---

## 1. 生成物

### フロントエンド（`src/frontend/`、React 18 + TypeScript strict + Vite）
- **雛形**: `package.json`, `tsconfig.json`（strict + noUncheckedIndexedAccess + exactOptionalPropertyTypes）, `vite.config.ts`, `eslint.config.js`, `index.html`, `.gitignore`, `vite-env.d.ts`
- **api/**: `types.ts`（U-07 DTO の TS 写像）, `client.ts`（ApiClient: 401 捕捉・credentials include・型付き ErrorResponse・CSV 生バイト）, `converters.ts`（DTO↔ビューモデル純関数）, `validation.ts`（FE-* クライアント検証）
- **app/**: `AuthContext.tsx`, `apiContext.ts`, `queryClient.ts`（retry 無効=fail-closed）, `ErrorBoundary.tsx`, `AppShell.tsx`, `App.tsx`（ルート表）, `main.tsx`
- **components/**: `Feedback.tsx`（ErrorBanner/LoadingIndicator/EmptyState/RowErrorList/ViolationList）, `CsvImportPanel.tsx`
- **hooks/**: `useJobStatus.ts`（`refetchInterval` で 2 秒ポーリング、終端で停止）
- **views/**: V-01〜V-07（Login/Event/Masters/Declarations/Sufficiency/Optimize/Assignments）
- **styles/**: `global.css`（WCAG 2.1 AA コントラスト・フォーカス）
- **tests/**（Vitest + Testing Library + fast-check）: 写像/検証の PBT 2 本、コンポーネントテスト 3 本（Login 401、CSV 行エラー、手動修正の制約違反）

計: ソース 22 ファイル、テスト 7 ファイル。

### バックエンド追加（`src/api_orchestration/`、in-place）
- **U08-H1**: `POST/GET /masters/facilities/import,export`、`POST/GET /masters/districts/import,export` を追加（`routers.py`）。`services.py` に `export_facilities_csv`/`export_districts_csv`、`composition.py` で U-03 の既存サービスに配線（**エクスポートは全て `sanitize_csv_cell` 経由** — P-API07 を新パスでも維持）。`tests/api_orchestration/test_masters.py`（5 テスト）。
- **U08-H4**: `composition.py` の `_mount_frontend` が `src/frontend/dist` 存在時のみ `StaticFiles` をマウント（未ビルド・テスト時は無効）。`config.py` に `frontend_dist_path`。

---

## 2. 品質ゲート結果

### フロント（TypeScript）
| ゲート | 結果 |
|-------|------|
| `tsc --noEmit`（strict） | **clean** |
| `eslint`（H-5 境界 + react/no-danger） | **clean** |
| `vitest run` | **12 passed**（PBT 7 + コンポーネント 5） |
| **H-5 非空虚性** | バックエンド import 注入 → **eslint FAIL**、除去 → clean（証明済み） |

### バックエンド（Python、回帰なし）
| ゲート | 結果 |
|-------|------|
| `pytest` | **178 passed**（173 + U08-H1 の 5） |
| `mypy --strict` | **106 files clean** |
| `ruff` | **clean** |
| `lint-imports` | **14 契約 kept**（R-8 等維持） |

---

## 3. 生成中に見つけた不具合・逸脱

### (1) ミドルウェアが注入クロックを使っていなかった（実在の不具合、U07-H15）
再開日が 2026-07-23 になったことで発覚。`middleware.py` はセッション検証を `datetime.now(UTC)`（実時間）で行う一方、ルートとログインは注入クロックを使う。テストは `clock=lambda: NOW=2026-07-17` でセッションを作るため、実時間が NOW+8h(TTL) を超えた瞬間に**全セッションが期限切れ**となり、認証フローの全テストが 401 で失敗した（7/17 実行時は実時間も 7/17 で偶然一致していた）。
**修正（構造的）**: `register_middleware` が同一の注入クロックを受け取り、セッション期限とレート制限窓を一つのクロックで判定するようにした（`composition.py` が `services.clock` を渡す）。本番は実時間のまま。**「アプリ全体で単一クロック」原則**の適用。→ **U07-H15**。

### (2) スタイリングは CSS Modules ではなく単一グローバル CSS（U08-H6、逸脱）
NFR Design Q3=A は CSS Modules を選択したが、PoC の小さな画面数に対し、セマンティックなクラス名の単一 `global.css` を用いた。マークアップ構造は不変のため、後からコンポーネント単位の CSS Modules へ移行可能。**承認された決定からの逸脱として記録** — 必要なら CSS Modules 化を依頼可能。

### (3) `src/frontend/` は自己完結 npm プロジェクト（U08-H5、意図的逸脱）
リポジトリの `src/`・`tests/` 分割規約に対し、フロントは独自の `package.json`/`tsconfig`/`vite.config` を持つため、プロジェクト内に `src/` と `tests/` を持つ標準構成とした。Python ツール（mypy/ruff/pytest/lint-imports）は `.ts`/node_modules を対象にしないため干渉なし。

### (4) 価値提示は当面 objective/gap のみ（U08-H2、承認済み）
`AssignmentResponse` が移動時間・費用を持たないため、V-07 の「遠い→近い」移動負担の数値提示は未実装。V-06 由来の `objective_value`/`optimality_gap` を要約表示。応答拡張は将来課題。

---

## 4. 設計の要点（守ったこと）

- **H-5 は構造で強制**: ESLint `no-restricted-imports` がバックエンドへの import を lint FAIL にする。バックエンドの import-linter R-8（api_orchestration は frontend を import しない）と対をなし、双方向で境界を固定。非空虚性も確認済み。
- **XSS 安全**: `react/no-danger` を error に。サーバ／ユーザ文字列は全てテキスト描画。
- **401 の一元処理**: ApiClient が全 401 を捕捉し AuthContext に失効通知。各画面は個別処理しない（FE-50）。
- **fail-closed**: TanStack Query の retry を無効化（自動リトライなし、resiliency 拡張無効に整合）。
- **ポーリングは終端で停止**: `refetchInterval` が終端状態で false を返し、タイマを破棄。
- **バックエンドが真実の源**: クライアント検証は UX のみ。制約 C1〜C5 はフロントで判定せず、PATCH 応答の `violations` を表示（U07-H1 の一元解釈を尊重）。
- **自動化容易**: 対話要素に `data-testid` を付与。

---

## 5. 申し送り

- **U08-H1**: 実施済み（施設・小学校区エンドポイント）。
- **U08-H2**: `AssignmentResponse` に移動時間・費用を追加すれば V-07 で移動負担を数値提示可能（将来）。
- **U08-H3**: 比較レポート画面は U05-H6（履歴テーブル）解消後。DTO/converter は U-07 に実装済み。
- **U08-H4**: 実施済み（静的配信マウント、`dist` 存在時のみ）。
- **U08-H5**: `src/frontend/` は自己完結 npm プロジェクト。
- **U08-H6**: スタイリングは単一グローバル CSS（Q3=A の CSS Modules からの逸脱、要確認）。
- **U07-H15**: ミドルウェアが注入クロックを使うよう修正（単一クロック原則）。
- **H-5**: ESLint 境界で強制、非空虚性確認済み。
