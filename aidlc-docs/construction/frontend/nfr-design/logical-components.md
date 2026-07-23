# U-08 frontend — 論理コンポーネント（NFR Design）

**方針**: フロントはインフラ系コンポーネント（キュー・キャッシュサーバ・サーキットブレーカ）を持たない。以下は**アプリ内の論理コンポーネント**で、NFR パターン（`nfr-design-patterns.md`）を担う横断部品。UI コンポーネント階層は機能設計 `frontend-components.md` を参照。

各コンポーネントに `LC-FE-*` を付す。

---

## LC-FE-01 ApiClient
- **責務**: REST 呼び出しの単一窓口。`fetch` の薄いラッパ。
- **提供**:
  - ベース URL を外部化設定から解決（NFR-FE-M4 / NFR-M05）。
  - `credentials: 'include'` で HttpOnly Cookie 自動送信（PAT-FE-10）。
  - 全応答を検査し、**`401` を捕捉して失効通知**（PAT-FE-11）。
  - 非 2xx を型付き `ErrorResponse` に変換して返す（PAT-FE-13）。CSV 行エラー・制約違反もここで型付け。
  - CSV 取込は生バイト送信、CSV エクスポートは `text/csv` 受信。
- **依存**: なし（バックエンドを import しない、PAT-FE-14）。
- **対応 NFR**: NFR-FE-SEC1/SEC3、NFR-FE-A2、NFR-FE-M4。

## LC-FE-02 AuthContext / AppContext
- **責務**: 認証状態（anonymous/authenticated）と選択中イベント ID を保持し全画面へ配布。
- **提供**: `onUnauthorized()`（→ V-01 遷移）、`selectEvent(id)`、ログイン中ユーザ表示用情報。
- **対応 NFR**: NFR-FE-A2、PAT-FE-03/11。

## LC-FE-03 QueryClient（TanStack Query）
- **責務**: サーバー状態のキャッシュ・重複排除・再取得・ポーリングの実行基盤。
- **提供**: `useQuery`（フェッチ・`refetchInterval` ポーリング）、`useMutation`（書込 + invalidate）。
- **設定**: 既定の `staleTime`／リトライ無効（fail-closed、PAT-FE-20 に整合 — 自動リトライしない）。
- **対応 NFR**: NFR-FE-P1/P2/P3、NFR-FE-A3/A4、PAT-FE-01/02/04/30。

## LC-FE-04 PollingController（JobStatus クエリの薄いフック）
- **責務**: `useJobStatus(jobId)` — `refetchInterval` を状態依存で制御し、終端で停止。
- **提供**: ジョブ状態・最適性ギャップ・経過時間・診断（`detail`）を JobProgressPanel に供給。
- **対応 NFR**: NFR-FE-P2/A3、PAT-FE-02。

## LC-FE-05 型付き DTO 写像（api/types + converters）
- **責務**: U-07 の DTO に対応する TypeScript 型定義と、DTO ↔ ビューモデルの純関数変換。
- **提供**: `fromEventResponse`／`toEventRequest` 等。**fast-check の写像ラウンドトリップ PBT の対象**（P-API01 のフロント版）。
- **対応 NFR**: NFR-FE-M1、機能設計 domain-entities.md。

## LC-FE-06 ErrorBoundary + ErrorBanner
- **責務**: 描画時例外の捕捉（Boundary）と、API／ネットワークエラーの汎用表示（Banner、手動再試行）。
- **対応 NFR**: NFR-FE-A1、PAT-FE-13/20/50。

## LC-FE-07 境界強制（ビルド／lint 設定、コンポーネントではないが論理要素）
- **責務**: ESLint import 境界ルールで `src/frontend/` → バックエンド import を禁止（PAT-FE-14）。`react/no-danger` で XSS 危険 API を禁止（PAT-FE-12）。
- **検証**: 非空虚性（禁止 import 注入 → FAIL）。
- **対応 NFR**: NFR-FE-M3/SEC2、H-5。

---

## 依存関係（論理）

```text
Views/Components (frontend-components.md)
      │ 使う
      ▼
LC-FE-03 QueryClient ──uses──> LC-FE-01 ApiClient ──REST──> U-07（外部）
LC-FE-04 PollingController ─uses─> LC-FE-03
LC-FE-02 AuthContext <──401通知── LC-FE-01
LC-FE-05 DTO写像  （ApiClient の内外で純変換）
LC-FE-06 ErrorBoundary/Banner （全体を包む）
LC-FE-07 境界強制 （ビルド時、実行時コンポーネントではない）
```

- **インフラ系コンポーネントなし**: キュー／キャッシュサーバ／CB／メッセージングはバックエンド（U-07 のジョブキュー等）が持つ。フロントは保持しない。

---

## Code Generation への申し送り

- LC-FE-01〜06 を `src/frontend/src/`（`api/`, `app/`, `components/`）に実装。
- LC-FE-07 は `eslint.config`／`tsconfig` に実装し、**非空虚性テストを CI 手順に含める**。
- 継続申し送り: U08-H1（施設・小学校区エンドポイント）、U08-H2（AssignmentResponse 移動指標）、U08-H3（比較画面は U05-H6 後）、H-5（LC-FE-07 で強制）。
