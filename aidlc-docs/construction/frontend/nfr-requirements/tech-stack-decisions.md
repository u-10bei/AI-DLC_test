# U-08 frontend — 技術スタック決定

**決定日**: 2026-07-23
**根拠**: NFR Requirements 計画の回答 Q1=A / Q2=A / Q3=A / Q4=A / Q5=A。
**位置づけ**: **U01-H20 の決着**（フロントエンドの言語・フレームワーク・PBT フレームワークを U-08 で決定）。

---

## 1. 決定一覧

| 項目 | 決定 | 根拠 |
|------|------|------|
| 言語 | **TypeScript（strict モード）** | バックエンドの mypy strict と同等の型規律。DTO をそのまま型として写せる（BR-API02 の乖離検知に寄与） |
| UI フレームワーク | **React 18** | 主流・エコシステム最大。7 画面 + ジョブポーリングという状態を持つ SPA に十分。将来拡張に耐える |
| ビルドツール | **Vite** | 高速・設定最小。TypeScript ネイティブ |
| PBT フレームワーク | **fast-check** | TS/JS の PBT 標準。**PBT 拡張（ブロッキング）をフロントでも満たす**。DTO↔ビューモデル写像・フォーム検証のプロパティに用いる |
| コンポーネント/UI テスト | **Vitest + Testing Library** | Vite 統合・高速。fast-check と同一ランナーで実行可 |
| E2E（任意） | **Playwright** | 価値実証フロー（ログイン→…→割当）の通し検証。PoC では任意 |
| 対応ブラウザ | **モダンなエバーグリーンのみ**（最新 Chrome/Edge/Firefox） | 庁内で管理された環境。レガシー対応の負担を負わない |
| アクセシビリティ | **WCAG 2.1 AA を目標**（JIS X 8341-3 整合） | 自治体＝公共部門。PoC では実務的範囲で適用 |
| スタイリング | 軽量 CSS（CSS Modules または最小限のユーティリティ）。重い UI キットは必須としない | PoC のフットプリント最小化。Code Generation で確定 |
| HTTP クライアント | 標準 `fetch`（薄い `ApiClient` ラッパ） | 依存最小。Cookie 自動送信・401 捕捉・`ErrorResponse` 型付けを一箇所に集約 |
| ルーティング | クライアントサイドルータ（例: React Router） | 7 画面の SPA 遷移 |

---

## 2. バックエンドスタックとの関係

- **完全分離**: フロントは REST/JSON 経由でのみ U-07 と通信（NFR-M05）。Python 側の型・モジュールを import しない（**H-5**、Code Generation でリンタ／ビルド規則により機械検証）。
- **型の写像**: U-07 の DTO（`src/api_orchestration/dto.py`）に対応する TypeScript 型を `src/frontend/` 側で定義する。手書きで写す（自動生成は将来課題）。**バックエンドが契約の源**であり、フロント型が乖離したらテスト（写像 PBT）で検知する。
- **配信**: PoC ではビルド済み静的アセットを U-07 と同一サーバーから配信してよい（A-07）。実運用のバックエンド分離時も REST 境界により無変更。

---

## 3. ディレクトリ構成（予定、Code Generation で確定）

```text
src/frontend/
├── src/
│   ├── api/            ApiClient, 型（DTO の写像）
│   ├── views/          V-01..V-07 の Container
│   ├── components/     Presentational（共通含む）
│   ├── app/            AppShell, ルーティング, AuthContext
│   └── main.tsx
├── tests/              Vitest + Testing Library + fast-check
├── index.html
├── vite.config.ts
├── tsconfig.json       strict: true
└── package.json
```

- `config/` にバックエンドのベース URL を外部化（NFR-M03）。ビルド時／実行時いずれの注入方式にするかは Code Generation で確定。

---

## 4. 品質ゲート（フロント）

| ゲート | ツール | 対応するバックエンドの規律 |
|-------|-------|----------------------|
| 型検査 | `tsc --noEmit`（strict） | mypy --strict |
| リンタ | ESLint（+ TypeScript 用ルール） | ruff |
| 境界検査（H-5） | ビルド／リンタ規則で `src/frontend/` からバックエンド import を禁止 | import-linter（バックエンド側の R-8: api_orchestration が frontend を import しない、と対になる） |
| ユニット/コンポーネント | Vitest + Testing Library | pytest |
| PBT | fast-check | Hypothesis |

**注**: これらはフロント（TypeScript）ツールチェーンであり、バックエンドの 4 ゲート（pytest/mypy/ruff/lint-imports）とは別プロセス。Build and Test ステージで両者の実行手順を統合する。
