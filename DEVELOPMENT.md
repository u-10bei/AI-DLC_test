# 開発ガイド（DEVELOPMENT）

本書は**開発者向け**の注意事項・手順をまとめたものです。プロジェクトの概要・操作説明書は [`README.md`](README.md) を参照してください。

---

## ⚠️ ディレクトリ名の読み替え規則

設計文書はユニットを `shared-kernel`、`distance-cost` のようにハイフンで表記します。
一方 **Python のモジュール名にハイフンは使えません**（`import shared-kernel` は SyntaxError）。

**コード上はアンダースコアを使います。**

| 文書上のユニット名 | コード上のディレクトリ・パッケージ名 |
|------------------|--------------------------------|
| `shared-kernel` | `src/shared_kernel/` |
| `distance-cost` | `src/distance_cost/` |
| `data-management` | `src/data_management/` |
| `optimization-engine` | `src/optimization_engine/` |
| `comparison-report` | `src/comparison_report/` |
| `security` | `src/security/` |
| `api-orchestration` | `src/api_orchestration/` |
| `frontend` | `src/frontend/` |

---

## ディレクトリ構造

```text
.
├── pyproject.toml        依存とツール設定
├── .importlinter         ユニット境界の機械的強制
├── alembic/, alembic.ini DB マイグレーション
├── config/               外部化された設定（NFR-M03）
├── src/
│   ├── shared_kernel/        U-01: 全ユニットが共有する型
│   ├── distance_cost/        U-02
│   ├── data_management/      U-03
│   ├── optimization_engine/  U-04
│   ├── comparison_report/    U-05
│   ├── security/             U-06
│   ├── api_orchestration/    U-07: REST API・合成ルート
│   └── frontend/             U-08: React + TypeScript SPA（自己完結 npm プロジェクト）
├── tests/                バックエンドのユニット/結合/PBT テスト
└── aidlc-docs/           設計文書のみ（アプリコードは置かない）
```

アプリケーションコードはワークスペースルート配下にのみ置きます。`aidlc-docs/` には文書のみです。
`src/frontend/` は独自の `package.json`/`tsconfig` を持つ自己完結した npm プロジェクトで、内部に `src/` と `tests/` を持ちます（U08-H5）。

---

## バックエンド（Python）

### セットアップ

```bash
# uv を推奨（Poetry も可）
uv sync

# または pip
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 4 つの品質ゲート

すべて CI で強制されます。

```bash
# 単体・結合テスト（例示ベース + プロパティベース）
PYTHONPATH=src pytest                 # 181 passed

# 型検査（strict モード）
mypy                                  # Success: no issues found in 107 source files

# リンタ・フォーマッタ
ruff check src tests                  # All checks passed!

# ユニット境界の検証（R-1..R-8）
PYTHONPATH=src lint-imports           # Contracts: 14 kept, 0 broken.
```

### プロパティベーステストのシード

CI では**実行ごとにランダムなシード**を使います（`CI=true` でプロファイルが切り替わります）。
固定シードは実行を決定的にしますが、毎回同じ入力しか試さず、未知のバグを見つける能力を失います。

失敗時は Hypothesis がシードを出力します。再現するには:

```bash
pytest --hypothesis-seed=<出力されたシード>
```

---

## フロントエンド（TypeScript / React）

`src/frontend/` で実行します。

```bash
cd src/frontend
npm install            # 依存の取得

# 品質ゲート
npx tsc --noEmit       # 型検査（strict）
npx eslint .           # リンタ（H-5 境界 + react/no-danger）
npm test               # Vitest（fast-check PBT + コンポーネント）12 passed

# 本番ビルド（dist/ を生成 → バックエンドが配信、U08-H4）
npm run build

# 開発サーバ（API を :8000 へプロキシ）
npm run dev
```

### H-5 境界（フロント → バックエンド import 禁止）

`src/frontend/` はバックエンドユニットを import してはいけません（NFR-M05）。
ESLint の `no-restricted-imports` で機械的に禁止しており、バックエンドの import-linter R-8 と対をなします。
非空虚性確認: バックエンド import を注入すると eslint が失敗し、除去すると通ります。

---

## 実行（ローカル）

```bash
# API プロセス（U-01〜U-07 を含む）
uvicorn api_orchestration.asgi:app --port 8000
# ジョブワーカー（最適化計算を別プロセスで実行）
python -m api_orchestration.worker
# フロント: 方式A（Vite dev, デモ向き）または 方式B（build して backend が配信）
```

詳細は [`aidlc-docs/construction/build-and-test/build-instructions.md`](aidlc-docs/construction/build-and-test/build-instructions.md)。

---

## セキュリティ・個人情報の取り扱い（実装上の注意）

- **職員の氏名と居住小学校区は個人情報です。** `Staff.__repr__` は両者を伏字にします。
  誤って `logger.info(staff)` と書いても漏れません。
- `src/security/` は `shared_kernel.Staff` を import できません（`.importlinter` で強制）。
  監査ログに個人情報が到達する経路が構造的に存在しません。
- **データディレクトリは暗号化ボリューム上に配置してください**（`app.db` と `audit/`）。
  詳細は [`aidlc-docs/construction/shared-infrastructure.md`](aidlc-docs/construction/shared-infrastructure.md)。
- 監査ログは追記専用ファイル（`chattr +a`）です。アプリケーションは追記のみ可能で、削除できません。
- **デプロイ時**: 公開基盤（TLS/WAF）の背後では `AppConfig.trusted_proxies` を必ず設定してください。
  未設定だと送信元 IP 判定がプロキシのアドレスになり、許可リストが全アクセスを遮断します（安全側に倒れる設計）。
- CSV エクスポートは数式インジェクション対策として無害化されます（MU-02）。

---

## アーキテクチャの要点

- **ヘキサゴナル（ポート & アダプター）**。ユニット依存は常に番号の小さい方へ向かい、循環しません。
- **U-01 のプロダクション依存はゼロ**（標準ライブラリのみ）。Pydantic は U-07 の API 境界に閉じ込めています。
  SQLite を PostgreSQL に、Web フレームワークを替えても U-01 は変わりません。
- モノリスでもモジュール境界は規約だけでは守られないため、**import-linter（バックエンド）と ESLint（フロント）で機械的に強制**します。

---

## 非公開ドキュメント（`private/`）

運用・デプロイに関する文書は、リポジトリ直下の **`private/`** に置きます。
`.gitignore` で **ディレクトリごと除外**しているため、ここに追加した文書は自動的に非公開です。

```text
private/
├── deployment-plan.md      デプロイ計画（決定事項・前提変更・作業項目）
└── deployment-runbook.md   Azure VM へのデプロイ手順書
```

**なぜ公開しないか**: ホスト名・ファイルパス・受け入れ確認の観点・障害時の挙動に加え、
「この構成に WAF は無い」「アクセス制御が何に依存しているか」という**構成の弱点の棚卸し**を
含みます。コードと並べて公開すると、読み手より攻撃者に利する情報になります。

**注意**:
- `private/` は git 管理外です。**バックアップは各自で確保してください**（消えると再作成が必要）。
- デプロイや運用の詳細を追記する際は、**必ず `private/` 配下に書いてください**。
  公開側の文書（`aidlc-docs/` や README）に書くと、そのまま公開されます。

---

## 申し送り（実運用に向けて）

本 PoC で未提供・要検討の項目。詳細は `aidlc-docs/aidlc-state.md` の各ハンドオフを参照。

- **U05-H6**: 比較レポートの履歴テーブル（`historical_assignments` / `historical_declarations`）→ 比較画面（US-26/27/28）の前提。
- **U08-H2**: 割当応答への移動時間・費用の付与（割当画面での移動負担の数値表示）。
- **U08-H6**: スタイリングを CSS Modules 化するか（現状は単一グローバル CSS）。
- **U06-H5**: 本番のアカウント払い出し（OS レベル運用）。
- **CI**: pip-audit / SBOM（SECURITY-10）、負荷試験の組み込み。
- **未提供の画面/機能**: イベント編集/削除（US-06）、マスタ個別修正（US-10）、申告履歴（US-12）、割当 CSV 出力（US-25）。
