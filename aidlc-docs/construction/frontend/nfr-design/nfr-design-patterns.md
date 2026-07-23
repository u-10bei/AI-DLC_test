# U-08 frontend — NFR 設計パターン

**ユニット**: U-08 frontend
**決定**: Q1=A（TanStack Query + Context）／ Q2=A（ESLint import 境界）／ Q3=A（CSS Modules）。
**スタック**: React 18 + TypeScript(strict) + Vite。

各パターンに `PAT-FE-*` を付す。対応する NFR 要件を併記。

---

## 1. 状態管理パターン（Performance / Logical、Q1=A）

### PAT-FE-01 サーバー状態は TanStack Query に集約
- フェッチ結果（イベント・充足・割当・ジョブ状態）は **TanStack Query** の `useQuery` で管理。キャッシュ・重複排除・ローディング／エラー状態を一元化。
- **対応**: NFR-FE-P1（初期表示）、NFR-FE-P3（一覧描画）、NFR-FE-A1（エラー表示）。

### PAT-FE-02 ジョブポーリングは `refetchInterval`
- 最適化ジョブ状態は `useQuery(..., { refetchInterval })` で約 2 秒間隔ポーリング。**終端状態（SUCCEEDED/INFEASIBLE/FAILED）に達したら `refetchInterval` を false にして停止**。
- 画面離脱でクエリが非アクティブ化 → ポーリング自動停止。再訪時 `job_id` があれば再開。
- **対応**: NFR-FE-P2、NFR-FE-A3。機能設計 §4 のポーリングロジックを実装。

### PAT-FE-03 クライアント状態は React Context
- 認証状態・選択中イベント ID は **AuthContext / AppContext** で保持。フォーム入力は各コンポーネントのローカル状態。
- サーバー状態とクライアント状態を混在させない（TanStack Query = サーバー、Context/local = クライアント）。
- **対応**: NFR-FE-A2、機能設計 §3。

### PAT-FE-04 ミューテーションと再取得
- 書込（ログイン、イベント作成、CSV 取込、最適化投入、手動修正）は `useMutation`。成功時に関連クエリを **invalidate** して再取得（例: 手動修正 → 割当一覧を invalidate）。
- 非終端ジョブ中・送信中は対象ボタンを無効化（多重送信防止）。
- **対応**: NFR-FE-A4、FE-35。

---

## 2. セキュリティ設計パターン（Security、Q2=A）

### PAT-FE-10 トークン非保持
- セッションは HttpOnly Cookie。`fetch` は `credentials: 'include'` で Cookie を自動送信。JS はトークンに触れない。
- **対応**: NFR-FE-SEC1、FE-52、BR-API21。

### PAT-FE-11 401 の一元捕捉
- **ApiClient** が全応答を検査し、`401` を捕捉して AuthContext に失効通知 → V-01 へ遷移。各画面は個別に 401 を処理しない。
- **対応**: NFR-FE-A2、FE-50。

### PAT-FE-12 XSS 安全描画
- React の既定エスケープに依拠。**`dangerouslySetInnerHTML` を使わない**。サーバー／ユーザ由来文字列はすべてテキストとして描画。
- ESLint で `react/no-danger` を有効化し、違反を lint で検出。
- **対応**: NFR-FE-SEC2。

### PAT-FE-13 エラー非開示
- ApiClient は `ErrorResponse` を型付きで返し、UI はその `message`／`violations`／`errors` をそのまま表示。フロントで内部状態（スタック・パス）を作らない・出さない。
- **対応**: NFR-FE-SEC3、FE-53、SECURITY-09。

### PAT-FE-14 H-5 境界の機械強制（ESLint import 境界）
- **ESLint の `no-restricted-imports`（または `eslint-plugin-import` の境界ルール）** で、`src/frontend/` から `src/`（バックエンドユニット）への import を禁止。lint ゲートで失敗させる。
- TypeScript 版の import-linter に相当し、バックエンドの **R-8**（api_orchestration は frontend を import しない）と対をなす。
- **非空虚性を確認**: 禁止 import を注入 → lint FAIL、除去 → PASS（Code Generation で実施）。
- **対応**: NFR-FE-M3、H-5。

---

## 3. レジリエンスパターン（Resilience: N/A の具体化）

### PAT-FE-20 fail-closed・手動再試行
- resiliency 拡張は無効（CQ4=A）。**自動リトライ・サーキットブレーカを持たない**。
- エラー時は ErrorBanner で汎用表示 + **手動**再試行ボタン。プロジェクト全体の fail-closed 方針に一致。
- **対応**: NFR-FE-A1。

---

## 4. 性能パターン（Performance）

### PAT-FE-30 キャッシュと重複排除
- TanStack Query のキャッシュで、同一データの重複フェッチを抑制。`staleTime` を適切に設定し不要な再取得を避ける。

### PAT-FE-31 バンドル最小化
- 重い UI キットを避け（CSS Modules、PAT-FE-40）、コード分割（ルート単位の lazy import）を必要に応じて適用。
- **対応**: NFR-FE-P4。

---

## 5. アクセシビリティパターン（Usability、WCAG 2.1 AA）

### PAT-FE-40 スタイリングは CSS Modules
- スコープ付き CSS Modules（ランタイムなし、重い依存なし）。コントラスト比を AA 基準で確保。
- **対応**: NFR-FE-P4、NFR-FE-U2。

### PAT-FE-41 セマンティック構造とフォーカス管理
- セマンティック HTML（`<form>`, `<label>`, `<table>`, `<nav>`, 見出し階層）、フォーム項目のラベル関連付け、キーボード操作、エラー時のフォーカス移動、`aria-live` によるジョブ状態・エラーの通知。
- **対応**: NFR-FE-U2、NFR-FE-U3。

---

## 6. エラーバウンダリ（Reliability）

### PAT-FE-50 React Error Boundary
- 描画時例外を Error Boundary で捕捉し、アプリ全体のクラッシュを防いで汎用エラー画面を表示。API エラー（PAT-FE-13）とは別レイヤ。
- **対応**: NFR-FE-A1。

---

## 7. NFR 要件 → パターン トレース

| NFR 要件 | パターン |
|---------|---------|
| NFR-FE-P1/P3 | PAT-FE-01, PAT-FE-30 |
| NFR-FE-P2 | PAT-FE-02 |
| NFR-FE-P4 | PAT-FE-31, PAT-FE-40 |
| NFR-FE-A1 | PAT-FE-20, PAT-FE-50 |
| NFR-FE-A2 | PAT-FE-03, PAT-FE-11 |
| NFR-FE-A3 | PAT-FE-02 |
| NFR-FE-A4 | PAT-FE-04 |
| NFR-FE-SEC1 | PAT-FE-10 |
| NFR-FE-SEC2 | PAT-FE-12 |
| NFR-FE-SEC3 | PAT-FE-13 |
| NFR-FE-U2/U3 | PAT-FE-40, PAT-FE-41 |
| NFR-FE-M3 / H-5 | PAT-FE-14 |
