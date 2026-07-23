# U-08 frontend — NFR Design 計画

**ユニット**: U-08 frontend（`src/frontend/`）
**ステージ**: NFR Design（NFR 要件を具体的な設計パターン・論理コンポーネントへ落とす）。
**スタック**: React 18 + TypeScript(strict) + Vite / fast-check / Vitest + Testing Library（`tech-stack-decisions.md`）。

---

## 1. NFR カテゴリの適用性評価（ルール要求: 全カテゴリを評価）

| カテゴリ | 適用 | 判断 |
|---------|------|------|
| **Resilience Patterns** | **N/A** | resiliency 拡張は無効（Requirements CQ4=A）。プロジェクト方針は fail-closed で**自動リトライ・サーキットブレーカを持たない**。フロントもこれに倣い、エラー時は汎用表示 + **手動**再試行導線のみ（自動再試行しない）。NFR-FE-A1 参照。 |
| **Scalability Patterns** | **N/A** | 利用者は数名規模（P-01/P-02）。水平スケール・負荷分散は不要（NFR-FE-S1/S2）。重い計算はバックエンド。 |
| **Performance Patterns** | **適用** | フェッチ／ポーリング（2 秒間隔）の状態管理方式が要決定 → **質問 1**。一覧描画・バンドルサイズは NFR-FE-P で明文化済み。 |
| **Security Patterns** | **適用** | 認証・認可・IP 制限等はバックエンド。フロントは (a) トークン非保持・XSS 安全描画（React 既定エスケープ、`dangerouslySetInnerHTML` 不使用）、(b) **H-5 境界の機械強制** が要決定 → **質問 2**。 |
| **Logical Components** | **適用** | ApiClient（401 捕捉・エラー型付け）、AuthContext、ポーリング制御、DTO↔ビューモデル写像。インフラ系（キュー/キャッシュ/CB）は持たない。スタイリング方式 → **質問 3**。 |

---

## 2. NFR 設計ステップ（完了ごとに [x]）

- [x] **ステップ A** — サーバー状態／クライアント状態の管理パターン確定（質問 1）と、ポーリング制御・401 捕捉の設計。
- [x] **ステップ B** — セキュリティ設計パターン: XSS 安全描画方針、**H-5 境界の機械強制方式**（質問 2）。
- [x] **ステップ C** — 論理コンポーネント設計: ApiClient、AuthContext、PollingController、型付き DTO 写像、ErrorBoundary、スタイリング（質問 3）。
- [x] **ステップ D** — 性能パターン: フェッチのキャッシュ／重複排除、非終端ジョブ中のボタン無効化、一覧描画の方針。
- [x] **ステップ E** — アクセシビリティ設計パターン（WCAG 2.1 AA を満たすセマンティック構造・フォーカス管理・ラベル・コントラスト）。
- [x] **ステップ F** — 成果物作成: `nfr-design-patterns.md`、`logical-components.md`。

---

## 3. 質問

各質問の `[Answer]:` タグの後に letter を記入してください。当てはまるものがなければ最後の選択肢（Other）を選び記述してください。

## 質問 1
サーバー状態（フェッチ結果・ジョブポーリング）とクライアント状態（認証・選択中イベント・フォーム）の管理方式はどれにしますか？

A) **TanStack Query（React Query）でサーバー状態 + React Context でクライアント状態** — フェッチ・キャッシュ・2 秒ポーリング（`refetchInterval`）・重複排除を専用ライブラリが担い、定型コードが最小。認証／選択中イベントは Context。

B) **React Context + hooks のみ（追加データライブラリなし）** — フェッチ／ポーリングを自作。依存最小だが手書きコードが増える。

C) **Redux Toolkit（+ RTK Query）** — より構造化・大規模向け。7 画面には過剰になりうる。

D) その他（[Answer]: タグの後に記述してください）

[Answer]:A

## 質問 2
**H-5**（`src/frontend/` がバックエンドユニットを import しない）を機械的にどう強制しますか？（バックエンドの import-linter R-8「api_orchestration は frontend を import しない」と対）

A) **ESLint の import 境界ルール**（`eslint-plugin-import` / `no-restricted-imports` 等）でバックエンドパスへの import を禁止し、lint ゲートを失敗させる。TypeScript 版の import-linter に相当。**非空虚性を確認**（禁止 import を注入 → lint FAIL）。

B) **TypeScript の path 設定／別 tsconfig で分離するのみ**（lint での明示的禁止は置かない）。

C) その他（[Answer]: タグの後に記述してください）

[Answer]:A

## 質問 3
スタイリング方式はどれにしますか？（NFR-FE-P4: 過大な UI キットを避ける、NFR-FE-U2: WCAG 2.1 AA）

A) **プレーンな CSS Modules**（スコープ付き、ランタイムなし、重い依存なし） — PoC に最小。

B) **ユーティリティ CSS フレームワーク**（例: Tailwind CSS）。

C) **コンポーネントライブラリ**（例: MUI） — UI 構築は速いが重く、アクセシビリティは既製に依存。

D) その他（[Answer]: タグの後に記述してください）

[Answer]:A
