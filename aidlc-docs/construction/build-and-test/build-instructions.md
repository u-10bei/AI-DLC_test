# Build Instructions

本システムは**モノリスなバックエンド（Python）+ フロントエンド SPA（TypeScript）**の 2 ビルド系からなる。両者は REST 境界でのみ結合する（NFR-M05）。

## Prerequisites

| 対象 | ツール | 確認済みバージョン |
|------|-------|------------------|
| バックエンド | Python | 3.12 |
| バックエンド | 依存管理 | `pip`（`pyproject.toml`） |
| フロントエンド | Node.js | v22.18.0 |
| フロントエンド | npm | 10.9.3 |

- **環境変数**: フロントのバックエンド URL は `VITE_API_BASE_URL`（未設定=同一オリジン）。バックエンドは `AppConfig`（`config/`、NFR-M03）。
- **システム要件**: Linux、数百 MB のディスク（node_modules 含む）。GPU 不要。

---

## Build Steps

### 1. 依存関係のインストール

```bash
# バックエンド（リポジトリルート）
pip install -e .            # pyproject.toml の依存（fastapi, sqlalchemy, ortools, argon2-cffi, hypothesis 等）

# フロントエンド
cd src/frontend
npm install                 # 407 packages（約 15 秒）
```

### 2. 環境設定

```bash
# バックエンドは既定値で起動可（SQLite インメモリ/ファイル）。本番は AppConfig を上書き。
# フロント URL を分離構成にする場合のみ:
export VITE_API_BASE_URL="https://backend.example.lan"
```

### 3. 全ユニットのビルド

```bash
# バックエンド: コンパイル成果物は無し（Python）。ビルド＝型検査 + リンタ + 依存契約。
python -m mypy --strict src tests
python -m ruff check
PYTHONPATH=src lint-imports

# フロントエンド: 型検査込みの本番ビルド
cd src/frontend
npm run build               # tsc --noEmit && vite build -> src/frontend/dist/
```

### 4. ビルド成功の確認

- **バックエンド**: `mypy` = `Success: no issues found in 107 source files`、`ruff` = `All checks passed!`、`lint-imports` = `Contracts: 14 kept, 0 broken.`
- **フロントエンド**: `dist/index.html` と `dist/assets/*`（JS 約 231 KB / gzip 約 73 KB、CSS 約 1.7 KB）が生成される。
- **配信（U08-H4）**: `dist/` が存在すると、バックエンドの API プロセスが同一サーバーから SPA を配信する（`AppConfig.frontend_dist_path`）。認証は API のみを保護し、SPA シェル・静的アセットは認証なしで読み込める（IP 制限・レート制限は適用、U08-H7）。

**受け入れ済みの警告**:
- `StarletteDeprecationWarning: Using httpx with starlette.testclient` — テスト実行時のみ、無害。
- npm の deprecation 警告（`whatwg-encoding` 等、推移的依存）— 無害。

---

## 実行（PoC）

```bash
# 方式A（推奨・デモ用）: フロントは Vite dev、API 呼び出しを :8000 の backend にプロキシ
uvicorn api_orchestration:build_application --factory --port 8000   # 別ターミナル
cd src/frontend && npm run dev                                      # Vite が SPA を配信

# 方式B（本番類似・単一サーバー）: フロントをビルドし backend が dist を配信
cd src/frontend && npm run build
# backend 起動時に AppConfig.frontend_dist_path=src/frontend/dist（既定）→ GET / が SPA を返す
```

ワーカープロセス（最適化ジョブ実行）は別プロセスで起動する（`python -m api_orchestration.worker`、shared-infrastructure.md §2）。

---

## Troubleshooting

### 依存エラー（バックエンド）
- **原因**: ortools が protobuf を、pydantic が litellm/mcp をダウングレードしうる（環境ノート済み、本プロジェクトには無関係）。
- **対処**: クリーンな venv で `pip install -e .`。

### コンパイルエラー（フロント）
- **原因**: `tsconfig` は strict + `exactOptionalPropertyTypes` + `noUncheckedIndexedAccess`。オプショナルへ `undefined` 代入等で失敗しうる。
- **対処**: `npx tsc --noEmit` のエラー箇所を修正。

### 依存契約 BROKEN（lint-imports）
- **原因**: ユニット境界を跨ぐ import を追加した。
- **対処**: `lint-imports` の BROKEN 契約が示す import を除去（R-1..R-8）。
