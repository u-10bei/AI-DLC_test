# 居住地考慮型 従事者割当最適化システム（PoC）

災害時の避難所応援職員の割当を、**職場単位**から**居住地を考慮した数理最適化**に置き換える PoC です。

現行方式では職員の居住地が割当に一切考慮されず、居住地から遠い施設に派遣されることで、
①移動時間による職員の負担増、②タクシー等の移動費用の高額化 が生じています。
本システムは、割当を一般化割当問題として解き、削減効果を数値で示します。

設計文書は [`aidlc-docs/`](aidlc-docs/) にあります。

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
├── config/               外部化された設定（NFR-M03）
├── src/
│   └── shared_kernel/    U-01: 全ユニットが共有する型
└── tests/
    └── shared_kernel/
```

アプリケーションコードはワークスペースルート配下にのみ置きます。`aidlc-docs/` には文書のみです。

---

## ユニット構成

モノリスですが、内部は8つのユニットに分割されています。依存は常に番号の小さい方へ向かい、循環しません。

| # | ユニット | 責務 | 依存 |
|---|---------|------|------|
| U-01 | `shared_kernel` | 全ユニットが共有する型・例外・列挙値変換表 | なし（根） |
| U-02 | `distance_cost` | 距離・移動時間・移動費用の算出（純粋関数） | U-01 |
| U-03 | `data_management` | 永続化と CSV 一括処理 | U-01, U-02 |
| U-04 | `optimization_engine` | 割当最適化、制約検証、実行不可能性の診断 | U-01〜U-03 |
| U-05 | `comparison_report` | ベースライン再現と削減効果の算出 | U-01, U-03, U-04 |
| U-06 | `security` | 認証・認可・ネットワーク統制・監査ログ | U-01 |
| U-07 | `api_orchestration` | REST API、割当結果の調整、設定管理 | U-01〜U-06 |
| U-08 | `frontend` | Web UI | U-07（REST 経由のみ） |

**現在の実装状況**: U-01 のみ完成。U-02 以降は未着手。

---

## 技術スタック

| 項目 | 選択 | 理由 |
|------|------|------|
| 言語 | Python | 40万の0-1変数を扱える MILP ソルバーが実質 Python と Java に限られ、PBT フレームワーク（Hypothesis）の品質で Python が優位 |
| Web | FastAPI + Pydantic | 型注釈に基づく入力検証 |
| DB | SQLite（PoC）→ PostgreSQL（実運用） | SQLAlchemy + Alembic 経由。移行は接続文字列の変更で済む |
| PBT | Hypothesis | カスタム生成器、シュリンキング、シード再現性 |
| 型検査 | mypy strict | U-01 の型が6ユニットを拘束するため、破壊的変更を CI で検出 |
| 境界強制 | import-linter | モノリスではモジュール境界は規約だけでは守られない |

**U-01 のプロダクション依存はゼロです**（標準ライブラリのみ）。Pydantic は U-07 の API 境界に閉じ込めています。
これにより、SQLite を PostgreSQL に替えても、Web フレームワークを替えても、U-01 は変わりません。

---

## セットアップ

```bash
# 依存のインストール（uv を推奨。Poetry も可）
uv sync

# または pip
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## テストと検証

4つのゲートすべてが CI で強制されます。

```bash
# 単体テスト（例示ベース + プロパティベース）
PYTHONPATH=src pytest

# 型検査（strict モード）
mypy

# リンタ・フォーマッタ
ruff check src tests

# ユニット境界の検証（R-2, R-3 ...）
PYTHONPATH=src lint-imports
```

### プロパティベーステストのシード

CI では**実行ごとにランダムなシード**を使います（`CI=true` でプロファイルが切り替わります）。
固定シードは実行を決定的にしますが、毎回同じ入力しか試さず、未知のバグを見つける能力を失います。

失敗時は Hypothesis がシードを出力します。再現するには:

```bash
pytest --hypothesis-seed=<出力されたシード>
```

---

## セキュリティ上の注意

- **職員の氏名と居住小学校区は個人情報です。** `Staff.__repr__` は両者を伏字にします。
  誤って `logger.info(staff)` と書いても漏れません。
- `src/security/` は `shared_kernel.Staff` を import できません（`.importlinter` で強制）。
  監査ログに個人情報が到達する経路が構造的に存在しません。
- **データディレクトリは暗号化ボリューム上に配置してください**（`app.db` と `audit/`）。
  詳細は [`aidlc-docs/construction/shared-infrastructure.md`](aidlc-docs/construction/shared-infrastructure.md)。
- 監査ログは追記専用ファイル（`chattr +a`）です。アプリケーションは追記のみ可能で、削除できません。
