# 居住地考慮型 従事者割当最適化システム（PoC）

災害時の避難所応援職員や選挙事務従事者の割当を、**職場単位**から**居住地を考慮した数理最適化**へ置き換える概念実証（PoC）です。

> **⚠️ 研修用 PoC** — 本リポジトリは AI-DLC ワークフローの学習・検証を目的としたサンプル実装です。実データ・本番利用を想定していません（データは仮名化）。

---

## 解決したい課題

現行方式では職員の居住地が割当に考慮されず、居住地から遠い施設に派遣されることで次の問題が生じています。

1. **移動時間**が長くなり、職員の負担が増える
2. **タクシー等の移動費用**が高額化する

本システムは割当を**一般化割当問題（GAP）**として解き、資格要件・従事可否・部署継続性などの制約を守りつつ移動負担を最小化し、**削減効果を数値で示します**。

> 検証例: 遠方に派遣されていた職員（移動 11,198 秒 / ¥37,326）が近隣（900 秒 / ¥0）へ最適化され、**移動時間 91.96% / 費用 100% 削減**（成功基準 SC-01）。

---

## 何ができるか（画面）

| 画面 | できること |
|------|-----------|
| ログイン | 庁内ネットワークからの認証 |
| イベント | 災害避難所応援・選挙事務のイベント登録 |
| マスタ | 職員・施設・小学校区マスタの CSV 一括取込／出力 |
| 申告取込 | 従事可否申告の一括登録 |
| 充足状況 | 従事可能人数と必要人数の充足・不足の可視化 |
| 最適化 | 重み・制限時間を指定して割当を計算（進捗ポーリング） |
| 割当結果 | 割当の一覧表示と、制約を自動検証しながらの手動修正 |

---

## 📖 操作説明書

利用者の役割ごとに、要件に沿って「どの操作をどの画面で行うか」を説明しています。

| ペルソナ | 説明書 | 内容 |
|---------|--------|------|
| P-01 割当担当者 | [manual-P-01-coordinator.md](aidlc-docs/operations/manual-P-01-coordinator.md) | イベント作成〜割当確定までの主要操作 |
| P-02 システム管理者 | [manual-P-02-admin.md](aidlc-docs/operations/manual-P-02-admin.md) | マスタ管理・アクセス制御・監査・運用 |
| P-03 従事職員 | [manual-P-03-staff.md](aidlc-docs/operations/manual-P-03-staff.md) | 間接的受益者（本 PoC では非操作） |

- 索引・凡例: [`aidlc-docs/operations/README.md`](aidlc-docs/operations/README.md)
- 画面別の操作手順（項目・ボタン単位）: [`aidlc-docs/operations/screens/`](aidlc-docs/operations/screens/)

---

## アーキテクチャ概要

モノリスですが、内部は 8 つのユニットに分割されています。依存は常に番号の小さい方へ向かい、循環しません。

| # | ユニット | 責務 | 依存 |
|---|---------|------|------|
| U-01 | `shared_kernel` | 全ユニットが共有する型・例外・列挙値変換表 | なし（根） |
| U-02 | `distance_cost` | 距離・移動時間・移動費用の算出（純粋関数） | U-01 |
| U-03 | `data_management` | 永続化と CSV 一括処理 | U-01, U-02 |
| U-04 | `optimization_engine` | 割当最適化、制約検証、実行不可能性の診断 | U-01〜U-03 |
| U-05 | `comparison_report` | ベースライン再現と削減効果の算出 | U-01, U-03, U-04 |
| U-06 | `security` | 認証・認可・ネットワーク統制・監査ログ | U-01 |
| U-07 | `api_orchestration` | REST API、割当結果の調整、設定管理 | U-01〜U-06 |
| U-08 | `frontend` | Web UI（React + TypeScript） | U-07（REST 経由のみ） |

- **ヘキサゴナル（ポート & アダプター）**。U-01 のプロダクション依存はゼロ（標準ライブラリのみ）で、Pydantic は U-07 の API 境界に閉じ込めています。
- ユニット境界は**機械的に強制**します（バックエンド: import-linter、フロント→バックエンド import 禁止: ESLint）。

### 技術スタック

| 領域 | 選択 |
|------|------|
| バックエンド | Python 3.12 / FastAPI + Pydantic / SQLite→PostgreSQL（SQLAlchemy + Alembic） / OR-Tools CP-SAT |
| フロントエンド | React 18 + TypeScript / Vite / TanStack Query |
| 品質保証 | mypy strict・ruff・import-linter / Hypothesis・fast-check（プロパティベーステスト） |

---

## 実装状況

**U-01〜U-08 すべて完成**（INCEPTION → CONSTRUCTION → Build and Test → Operations 説明書）。全ゲート green。

| | 結果 |
|---|------|
| バックエンド | pytest **181 passed** / mypy strict（107 files）/ ruff / import-linter **14 契約** |
| フロントエンド | tsc / eslint / vitest **12 passed** |

詳細: [`aidlc-docs/construction/build-and-test/build-and-test-summary.md`](aidlc-docs/construction/build-and-test/build-and-test-summary.md)

---

## クイックスタート

```bash
# バックエンド（API + ワーカー）
uv sync
uvicorn api_orchestration:build_application --factory --port 8000   # API
python -m api_orchestration.worker                                   # 最適化ワーカー（別プロセス）

# フロントエンド
cd src/frontend && npm install && npm run dev                        # 開発サーバ（API を :8000 へプロキシ）
```

セットアップ・テスト・ビルドの詳細、開発上の注意は **[DEVELOPMENT.md](DEVELOPMENT.md)** を参照してください。

---

## ドキュメント

| 文書 | 内容 |
|------|------|
| [`aidlc-docs/`](aidlc-docs/) | 要件・ユーザーストーリー・設計・監査証跡（AI-DLC の全成果物） |
| [`aidlc-docs/operations/`](aidlc-docs/operations/) | 操作説明書（ペルソナ別・画面別） |
| [`aidlc-docs/construction/build-and-test/`](aidlc-docs/construction/build-and-test/) | ビルド・テスト手順とサマリ |
| [`aidlc-docs/construction/shared-infrastructure.md`](aidlc-docs/construction/shared-infrastructure.md) | デプロイ・インフラ・セキュリティ境界 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 開発ガイド（セットアップ・ゲート・実装上の注意・申し送り） |

---

## 注記

研修用 PoC のため、実データは扱わず、氏名等は仮名化しています。個人情報（居住地情報）の取り扱い・監査・アクセス制御は構造的に担保していますが、本番運用には別途の整備（アカウント運用、負荷試験、依存脆弱性スキャン等）が必要です。詳細は DEVELOPMENT.md の「申し送り」を参照してください。
